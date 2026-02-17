"""
WordPress Plugin

Complete WordPress management through REST API.
Supports posts, pages, media, users, plugins, themes, and settings.
"""

import base64
import json
from typing import Any

import aiohttp

from plugins.base import BasePlugin
from plugins.wordpress.wp_cli import WPCLIManager

class WordPressPlugin(BasePlugin):
    """
    WordPress project plugin.

    Provides comprehensive WordPress management capabilities including:
    - Content (posts, pages)
    - Media library
    - Users
    - Plugins
    - Themes
    - Settings
    - Site health
    """

    def get_plugin_name(self) -> str:
        return "wordpress"

    def get_required_config_keys(self) -> list[str]:
        return ["url", "username", "app_password"]

    def __init__(self, project_id: str, config: dict[str, Any]):
        super().__init__(project_id, config)

        # WordPress configuration
        self.site_url = config["url"].rstrip("/")
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.username = config["username"]
        self.app_password = config["app_password"]

        # Create auth header
        credentials = f"{self.username}:{self.app_password}"
        token = base64.b64encode(credentials.encode()).decode()
        self.auth_header = f"Basic {token}"

        # WooCommerce API base (uses same authentication)
        self.wc_api_base = f"{self.site_url}/wp-json/wc/v3"

        # Optional container name for WP-CLI access (Phase 5+)
        self.container_name = config.get("container")

        # WP-CLI Manager (optional - requires container)
        if self.container_name:
            self.wp_cli = WPCLIManager(self.container_name)
        else:
            self.wp_cli = None

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        data: Any | None = None,
        headers_override: dict | None = None,
        use_custom_namespace: bool = False,
    ) -> dict[str, Any]:
        """
        Make authenticated request to WordPress REST API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body data
            data: Raw data or FormData for file uploads
            headers_override: Override default headers
            use_custom_namespace: If True, use wp-json root instead of wp/v2

        Returns:
            Dict: API response

        Raises:
            Exception: On API errors
        """
        if use_custom_namespace:
            # For custom namespaces like seo-api-bridge/v1
            url = f"{self.site_url}/wp-json/{endpoint}"
        else:
            url = f"{self.api_base}/{endpoint}"
        headers = {"Authorization": self.auth_header}

        # Override headers if provided (useful for file uploads)
        if headers_override:
            headers.update(headers_override)

        # Filter out None values from params to avoid WordPress API validation errors
        # WordPress REST API doesn't accept None values in query parameters
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        # Also filter None values from JSON data for POST/PUT requests
        if json_data:
            json_data = {k: v for k, v in json_data.items() if v is not None}

        async with (
            aiohttp.ClientSession() as session,
            session.request(
                method, url, params=params, json=json_data, data=data, headers=headers
            ) as response,
        ):
            if response.status >= 400:
                error_text = await response.text()
                raise Exception(f"WordPress API error ({response.status}): {error_text}")

            return await response.json()

    async def health_check(self) -> dict[str, Any]:
        """Check WordPress site health, WooCommerce, and SEO plugins availability."""
        try:
            # Check WordPress site info
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.site_url}/wp-json") as response:
                    if response.status == 200:
                        data = await response.json()

                        # Check WooCommerce status
                        woo_status = await self.check_woocommerce()

                        # Check SEO plugins status
                        seo_status = await self.check_seo_plugins()

                        return {
                            "healthy": True,
                            "wordpress": {
                                "accessible": True,
                                "name": data.get("name", "Unknown"),
                                "version": data.get("description", "Unknown version"),
                            },
                            "woocommerce": woo_status,
                            "seo_plugins": seo_status,
                        }
                    else:
                        return {
                            "healthy": False,
                            "message": f"Site returned status {response.status}",
                        }
        except Exception as e:
            return {"healthy": False, "message": f"Health check failed: {str(e)}"}

    def get_tools(self) -> list[dict[str, Any]]:
        """Return all WordPress tools."""
        return [
            # === POSTS ===
            {
                "name": self._create_tool_name("list_posts"),
                "description": f"List WordPress posts from {self.project_id}. Returns paginated list of posts with title, excerpt, status, and metadata.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "Number of posts per page (1-100)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "default": 1,
                            "minimum": 1,
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by post status",
                            "enum": ["publish", "draft", "pending", "private", "any"],
                            "default": "any",
                        },
                        "search": {"type": "string", "description": "Search term to filter posts"},
                    },
                },
                "handler": self.list_posts,
            },
            {
                "name": self._create_tool_name("get_post"),
                "description": f"Get detailed information about a specific WordPress post from {self.project_id}. Returns full post content, metadata, author, categories, tags, and featured image.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_id": {"type": "integer", "description": "Post ID", "minimum": 1}
                    },
                    "required": ["post_id"],
                },
                "handler": self.get_post,
            },
            {
                "name": self._create_tool_name("create_post"),
                "description": f"Create a new WordPress post in {self.project_id}. Supports HTML content, categories, tags, featured images, and scheduling.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Post title (displayed as main heading)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Post content (supports HTML and WordPress blocks)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Publication status of the post",
                            "enum": ["publish", "draft", "pending", "private"],
                            "default": "draft",
                        },
                        "slug": {
                            "type": "string",
                            "description": "Post URL slug (e.g., 'my-post-url'). If not provided, will be auto-generated from title.",
                        },
                        "excerpt": {
                            "type": "string",
                            "description": "Post excerpt (summary shown in listings and previews)",
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Array of category IDs to assign to the post",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Array of tag IDs to assign to the post",
                        },
                        "featured_media": {
                            "type": "integer",
                            "description": "Featured image media ID (post thumbnail)",
                        },
                    },
                    "required": ["title", "content"],
                },
                "handler": self.create_post,
            },
            {
                "name": self._create_tool_name("update_post"),
                "description": f"Update an existing WordPress post in {self.project_id}. Can update title, content, status, slug, categories, tags, and featured image.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "integer",
                            "description": "Post ID to update",
                            "minimum": 1,
                        },
                        "title": {
                            "type": "string",
                            "description": "Post title (displayed as main heading)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Post content (supports HTML and WordPress blocks)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Publication status of the post",
                            "enum": ["publish", "draft", "pending", "private"],
                        },
                        "slug": {
                            "type": "string",
                            "description": "Post URL slug (e.g., 'my-post-url')",
                        },
                        "excerpt": {
                            "type": "string",
                            "description": "Post excerpt (summary shown in listings and previews)",
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Array of category IDs to assign to the post",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Array of tag IDs to assign to the post",
                        },
                        "featured_media": {
                            "type": "integer",
                            "description": "Featured image media ID (post thumbnail)",
                        },
                    },
                    "required": ["post_id"],
                },
                "handler": self.update_post,
            },
            {
                "name": self._create_tool_name("delete_post"),
                "description": f"Delete a WordPress post from {self.project_id}. Can force delete or move to trash.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "integer",
                            "description": "Post ID to delete",
                            "minimum": 1,
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Whether to bypass trash and force deletion",
                            "default": False,
                        },
                    },
                    "required": ["post_id"],
                },
                "handler": self.delete_post,
            },
            # === PAGES ===
            {
                "name": self._create_tool_name("list_pages"),
                "description": f"List WordPress pages from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {"type": "integer", "default": 1, "minimum": 1},
                        "status": {
                            "type": "string",
                            "enum": ["publish", "draft", "pending", "private", "any"],
                            "default": "any",
                        },
                    },
                },
                "handler": self.list_pages,
            },
            {
                "name": self._create_tool_name("create_page"),
                "description": f"Create a new WordPress page in {self.project_id}. Supports HTML content, parent pages, and custom slugs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Page title (displayed as main heading)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Page content (supports HTML and WordPress blocks)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Publication status of the page",
                            "enum": ["publish", "draft", "pending", "private"],
                            "default": "draft",
                        },
                        "slug": {
                            "type": "string",
                            "description": "Page URL slug (e.g., 'about-us'). If not provided, will be auto-generated from title.",
                        },
                        "parent": {
                            "type": "integer",
                            "description": "Parent page ID for creating hierarchical page structure",
                        },
                    },
                    "required": ["title", "content"],
                },
                "handler": self.create_page,
            },
            {
                "name": self._create_tool_name("update_page"),
                "description": f"Update an existing WordPress page in {self.project_id}. Can update title, content, status, slug, and parent page.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "integer",
                            "description": "Page ID to update",
                            "minimum": 1,
                        },
                        "title": {
                            "type": "string",
                            "description": "Page title (displayed as main heading)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Page content (supports HTML and WordPress blocks)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Publication status of the page",
                            "enum": ["publish", "draft", "pending", "private"],
                        },
                        "slug": {
                            "type": "string",
                            "description": "Page URL slug (e.g., 'about-us')",
                        },
                        "parent": {
                            "type": "integer",
                            "description": "Parent page ID for hierarchical page structure",
                        },
                    },
                    "required": ["page_id"],
                },
                "handler": self.update_page,
            },
            # === MEDIA ===
            {
                "name": self._create_tool_name("list_media"),
                "description": f"List media library items from {self.project_id}. Returns images, videos, documents with URLs and metadata.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "Number of media items per page",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number for pagination",
                            "default": 1,
                            "minimum": 1,
                        },
                        "media_type": {
                            "type": "string",
                            "enum": ["image", "video", "audio", "application"],
                            "description": "Filter by media type (image, video, audio, or document)",
                        },
                    },
                },
                "handler": self.list_media,
            },
            {
                "name": self._create_tool_name("get_media"),
                "description": f"Get detailed information about a media item from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "media_id": {"type": "integer", "description": "Media ID", "minimum": 1}
                    },
                    "required": ["media_id"],
                },
                "handler": self.get_media,
            },
            {
                "name": self._create_tool_name("upload_media_from_url"),
                "description": f"Upload media from URL to {self.project_id} media library (sideload).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Public URL of the media file to upload (image, video, document, etc.)",
                        },
                        "title": {
                            "type": "string",
                            "description": "Media title (used in media library)",
                        },
                        "alt_text": {
                            "type": "string",
                            "description": "Alternative text for accessibility (important for images)",
                        },
                        "caption": {
                            "type": "string",
                            "description": "Media caption (displayed below image when inserted into content)",
                        },
                    },
                    "required": ["url"],
                },
                "handler": self.upload_media_from_url,
            },
            {
                "name": self._create_tool_name("update_media"),
                "description": f"Update media metadata in {self.project_id}. Supports title, description, slug, alt text, caption, status, and associated post.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "media_id": {
                            "type": "integer",
                            "description": "Media ID to update",
                            "minimum": 1,
                        },
                        "title": {
                            "type": "string",
                            "description": "Media title (displayed in media library)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Media description (full text content, displayed in attachment page)",
                        },
                        "slug": {
                            "type": "string",
                            "description": "Media URL slug (e.g., 'my-image-name')",
                        },
                        "alt_text": {
                            "type": "string",
                            "description": "Alternative text for accessibility (important for images)",
                        },
                        "caption": {
                            "type": "string",
                            "description": "Media caption (shown below image in content)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Publication status of the media",
                            "enum": ["publish", "draft", "private"],
                        },
                        "post": {
                            "type": "integer",
                            "description": "ID of the post/page to attach this media to",
                        },
                    },
                    "required": ["media_id"],
                },
                "handler": self.update_media,
            },
            {
                "name": self._create_tool_name("delete_media"),
                "description": f"Delete media from {self.project_id} library.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "media_id": {
                            "type": "integer",
                            "description": "Media ID to delete",
                            "minimum": 1,
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force permanent deletion",
                            "default": False,
                        },
                    },
                    "required": ["media_id"],
                },
                "handler": self.delete_media,
            },
            # === COMMENTS ===
            {
                "name": self._create_tool_name("list_comments"),
                "description": f"List comments from {self.project_id}. Filter by post, status, author.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {"type": "integer", "default": 1, "minimum": 1},
                        "post": {"type": "integer", "description": "Filter by post ID"},
                        "status": {
                            "type": "string",
                            "enum": ["approve", "hold", "spam", "trash", "all"],
                            "default": "approve",
                            "description": "Filter by comment status",
                        },
                    },
                },
                "handler": self.list_comments,
            },
            {
                "name": self._create_tool_name("get_comment"),
                "description": f"Get detailed information about a specific comment from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "comment_id": {"type": "integer", "description": "Comment ID", "minimum": 1}
                    },
                    "required": ["comment_id"],
                },
                "handler": self.get_comment,
            },
            {
                "name": self._create_tool_name("create_comment"),
                "description": f"Create a new comment in {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "integer",
                            "description": "Post ID to comment on",
                            "minimum": 1,
                        },
                        "content": {"type": "string", "description": "Comment content"},
                        "author_name": {"type": "string", "description": "Comment author name"},
                        "author_email": {"type": "string", "description": "Comment author email"},
                        "status": {
                            "type": "string",
                            "enum": ["approve", "hold"],
                            "default": "hold",
                            "description": "Comment status",
                        },
                    },
                    "required": ["post_id", "content"],
                },
                "handler": self.create_comment,
            },
            {
                "name": self._create_tool_name("update_comment"),
                "description": f"Update an existing comment in {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "comment_id": {
                            "type": "integer",
                            "description": "Comment ID to update",
                            "minimum": 1,
                        },
                        "content": {"type": "string", "description": "New comment content"},
                        "status": {
                            "type": "string",
                            "enum": ["approve", "hold", "spam", "trash"],
                            "description": "New comment status",
                        },
                    },
                    "required": ["comment_id"],
                },
                "handler": self.update_comment,
            },
            {
                "name": self._create_tool_name("delete_comment"),
                "description": f"Delete a comment from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "comment_id": {
                            "type": "integer",
                            "description": "Comment ID to delete",
                            "minimum": 1,
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force permanent deletion (bypass trash)",
                            "default": False,
                        },
                    },
                    "required": ["comment_id"],
                },
                "handler": self.delete_comment,
            },
            # === CATEGORIES ===
            {
                "name": self._create_tool_name("list_categories"),
                "description": f"List post categories from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {"type": "integer", "default": 1, "minimum": 1},
                        "hide_empty": {
                            "type": "boolean",
                            "default": False,
                            "description": "Hide categories with no posts",
                        },
                    },
                },
                "handler": self.list_categories,
            },
            {
                "name": self._create_tool_name("create_category"),
                "description": f"Create a new category in {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Category name"},
                        "description": {"type": "string", "description": "Category description"},
                        "parent": {
                            "type": "integer",
                            "description": "Parent category ID for hierarchy",
                        },
                    },
                    "required": ["name"],
                },
                "handler": self.create_category,
            },
            {
                "name": self._create_tool_name("update_category"),
                "description": f"Update an existing category in {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category_id": {
                            "type": "integer",
                            "description": "Category ID to update",
                            "minimum": 1,
                        },
                        "name": {"type": "string", "description": "New category name"},
                        "description": {
                            "type": "string",
                            "description": "New category description",
                        },
                        "parent": {"type": "integer", "description": "New parent category ID"},
                    },
                    "required": ["category_id"],
                },
                "handler": self.update_category,
            },
            {
                "name": self._create_tool_name("delete_category"),
                "description": f"Delete a category from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category_id": {
                            "type": "integer",
                            "description": "Category ID to delete",
                            "minimum": 1,
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force permanent deletion",
                            "default": False,
                        },
                    },
                    "required": ["category_id"],
                },
                "handler": self.delete_category,
            },
            # === TAGS ===
            {
                "name": self._create_tool_name("list_tags"),
                "description": f"List post tags from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {"type": "integer", "default": 1, "minimum": 1},
                        "hide_empty": {
                            "type": "boolean",
                            "default": False,
                            "description": "Hide tags with no posts",
                        },
                    },
                },
                "handler": self.list_tags,
            },
            {
                "name": self._create_tool_name("create_tag"),
                "description": f"Create a new tag in {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Tag name"},
                        "description": {"type": "string", "description": "Tag description"},
                    },
                    "required": ["name"],
                },
                "handler": self.create_tag,
            },
            {
                "name": self._create_tool_name("update_tag"),
                "description": f"Update an existing tag in {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tag_id": {
                            "type": "integer",
                            "description": "Tag ID to update",
                            "minimum": 1,
                        },
                        "name": {"type": "string", "description": "New tag name"},
                        "description": {"type": "string", "description": "New tag description"},
                    },
                    "required": ["tag_id"],
                },
                "handler": self.update_tag,
            },
            {
                "name": self._create_tool_name("delete_tag"),
                "description": f"Delete a tag from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tag_id": {
                            "type": "integer",
                            "description": "Tag ID to delete",
                            "minimum": 1,
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force permanent deletion",
                            "default": False,
                        },
                    },
                    "required": ["tag_id"],
                },
                "handler": self.delete_tag,
            },
            # === USERS ===
            {
                "name": self._create_tool_name("list_users"),
                "description": f"List WordPress users from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {"type": "integer", "default": 1, "minimum": 1},
                        "roles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by user roles",
                        },
                    },
                },
                "handler": self.list_users,
            },
            {
                "name": self._create_tool_name("get_current_user"),
                "description": f"Get information about the currently authenticated user in {self.project_id}.",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.get_current_user,
            },
            # === PLUGINS ===
            {
                "name": self._create_tool_name("list_plugins"),
                "description": f"List installed WordPress plugins in {self.project_id}. Shows plugin status (active/inactive), version, and details.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["active", "inactive", "all"],
                            "default": "all",
                        }
                    },
                },
                "handler": self.list_plugins,
            },
            # === THEMES ===
            {
                "name": self._create_tool_name("list_themes"),
                "description": f"List installed WordPress themes in {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["active", "inactive", "all"],
                            "default": "all",
                        }
                    },
                },
                "handler": self.list_themes,
            },
            {
                "name": self._create_tool_name("get_active_theme"),
                "description": f"Get information about the currently active theme in {self.project_id}.",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.get_active_theme,
            },
            # === SETTINGS ===
            {
                "name": self._create_tool_name("get_settings"),
                "description": f"Get WordPress site settings from {self.project_id}. Includes site title, description, URL, timezone, etc.",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.get_settings,
            },
            # === HEALTH ===
            {
                "name": self._create_tool_name("get_site_health"),
                "description": f"Check WordPress site health and accessibility for {self.project_id}.",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.get_site_health,
            },
            # ========================================
            # WooCommerce Tools
            # ========================================
            # === PRODUCTS ===
            {
                "name": self._create_tool_name("list_products"),
                "description": f"List WooCommerce products from {self.project_id}. Returns paginated product list with prices, stock status, and categories.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "Number of products per page (1-100)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "default": 1,
                            "minimum": 1,
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by product status",
                            "enum": ["any", "publish", "draft", "pending", "private"],
                            "default": "any",
                        },
                        "category": {"type": "integer", "description": "Filter by category ID"},
                        "stock_status": {
                            "type": "string",
                            "description": "Filter by stock status",
                            "enum": ["instock", "outofstock", "onbackorder"],
                        },
                        "search": {
                            "type": "string",
                            "description": "Search term to filter products",
                        },
                    },
                },
                "handler": self.list_products,
            },
            {
                "name": self._create_tool_name("get_product"),
                "description": f"Get detailed information about a specific WooCommerce product from {self.project_id}. Returns full product details including price, stock, categories, images, and attributes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"product_id": {"type": "integer", "description": "Product ID"}},
                    "required": ["product_id"],
                },
                "handler": self.get_product,
            },
            {
                "name": self._create_tool_name("create_product"),
                "description": f"Create a new WooCommerce product in {self.project_id}. Supports simple, variable, and grouped products with prices, stock, categories, and images.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Product name"},
                        "type": {
                            "type": "string",
                            "description": "Product type",
                            "enum": ["simple", "variable", "grouped", "external"],
                            "default": "simple",
                        },
                        "regular_price": {
                            "type": "string",
                            "description": "Regular price (as string, e.g., '19.99')",
                        },
                        "sale_price": {"type": "string", "description": "Sale price (as string)"},
                        "description": {
                            "type": "string",
                            "description": "Product description (HTML allowed)",
                        },
                        "short_description": {
                            "type": "string",
                            "description": "Short product description",
                        },
                        "status": {
                            "type": "string",
                            "description": "Product status",
                            "enum": ["publish", "draft", "pending", "private"],
                            "default": "draft",
                        },
                        "categories": {
                            "type": "array",
                            "description": "Array of category IDs",
                            "items": {"type": "integer"},
                        },
                        "tags": {
                            "type": "array",
                            "description": "Array of tag IDs",
                            "items": {"type": "integer"},
                        },
                        "stock_quantity": {"type": "integer", "description": "Stock quantity"},
                        "manage_stock": {
                            "type": "boolean",
                            "description": "Enable stock management",
                            "default": False,
                        },
                        "stock_status": {
                            "type": "string",
                            "description": "Stock status",
                            "enum": ["instock", "outofstock", "onbackorder"],
                            "default": "instock",
                        },
                    },
                    "required": ["name"],
                },
                "handler": self.create_product,
            },
            {
                "name": self._create_tool_name("update_product"),
                "description": f"Update an existing WooCommerce product in {self.project_id}. Can update name, price, stock, status, categories, and other product fields.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"},
                        "name": {"type": "string", "description": "Product name"},
                        "regular_price": {
                            "type": "string",
                            "description": "Regular price (as string)",
                        },
                        "sale_price": {"type": "string", "description": "Sale price (as string)"},
                        "description": {"type": "string", "description": "Product description"},
                        "short_description": {"type": "string", "description": "Short description"},
                        "status": {
                            "type": "string",
                            "description": "Product status",
                            "enum": ["publish", "draft", "pending", "private"],
                        },
                        "stock_quantity": {"type": "integer", "description": "Stock quantity"},
                        "stock_status": {
                            "type": "string",
                            "description": "Stock status",
                            "enum": ["instock", "outofstock", "onbackorder"],
                        },
                    },
                    "required": ["product_id"],
                },
                "handler": self.update_product,
            },
            {
                "name": self._create_tool_name("delete_product"),
                "description": f"Delete a WooCommerce product from {self.project_id}. Can force delete or move to trash.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"},
                        "force": {
                            "type": "boolean",
                            "description": "Force permanent delete (bypass trash)",
                            "default": False,
                        },
                    },
                    "required": ["product_id"],
                },
                "handler": self.delete_product,
            },
            # === PRODUCT CATEGORIES ===
            {
                "name": self._create_tool_name("list_product_categories"),
                "description": f"List WooCommerce product categories from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "Number of categories per page",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "default": 1,
                            "minimum": 1,
                        },
                        "hide_empty": {
                            "type": "boolean",
                            "description": "Hide categories with no products",
                            "default": False,
                        },
                    },
                },
                "handler": self.list_product_categories,
            },
            {
                "name": self._create_tool_name("create_product_category"),
                "description": f"Create a new WooCommerce product category in {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Category name"},
                        "description": {"type": "string", "description": "Category description"},
                        "parent": {"type": "integer", "description": "Parent category ID"},
                    },
                    "required": ["name"],
                },
                "handler": self.create_product_category,
            },
            # === PRODUCT TAGS ===
            {
                "name": self._create_tool_name("list_product_tags"),
                "description": f"List WooCommerce product tags from {self.project_id}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "Number of tags per page",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "default": 1,
                            "minimum": 1,
                        },
                        "hide_empty": {
                            "type": "boolean",
                            "description": "Hide tags with no products",
                            "default": False,
                        },
                    },
                },
                "handler": self.list_product_tags,
            },
            # === WOOCOMMERCE COUPONS ===
            {
                "name": self._create_tool_name("list_coupons"),
                "description": f"List WooCommerce coupons from {self.project_id}. Returns paginated coupon list with discount details and usage restrictions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "Number of coupons per page",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "default": 1,
                            "minimum": 1,
                        },
                        "search": {
                            "type": "string",
                            "description": "Search term to filter coupons by code",
                        },
                    },
                },
                "handler": self.list_coupons,
            },
            {
                "name": self._create_tool_name("create_coupon"),
                "description": f"Create a new WooCommerce coupon in {self.project_id}. Supports percentage and fixed discounts with usage limits and restrictions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Coupon code (e.g., 'SAVE20')"},
                        "discount_type": {
                            "type": "string",
                            "description": "Type of discount",
                            "enum": ["percent", "fixed_cart", "fixed_product"],
                            "default": "percent",
                        },
                        "amount": {
                            "type": "string",
                            "description": "Discount amount (e.g., '20' for 20% or $20)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Coupon description (internal note)",
                        },
                        "date_expires": {
                            "type": "string",
                            "description": "Expiration date in ISO 8601 format (e.g., '2024-12-31T23:59:59')",
                        },
                        "minimum_amount": {
                            "type": "string",
                            "description": "Minimum order amount required to use coupon",
                        },
                        "maximum_amount": {
                            "type": "string",
                            "description": "Maximum order amount allowed to use coupon",
                        },
                        "individual_use": {
                            "type": "boolean",
                            "description": "If true, coupon cannot be combined with other coupons",
                            "default": False,
                        },
                        "product_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Array of product IDs coupon applies to",
                        },
                        "excluded_product_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Array of product IDs coupon does NOT apply to",
                        },
                        "usage_limit": {
                            "type": "integer",
                            "description": "Maximum number of times coupon can be used",
                        },
                        "usage_limit_per_user": {
                            "type": "integer",
                            "description": "Maximum number of times coupon can be used per user",
                        },
                        "limit_usage_to_x_items": {
                            "type": "integer",
                            "description": "Maximum number of items coupon applies to",
                        },
                        "free_shipping": {
                            "type": "boolean",
                            "description": "If true, grants free shipping",
                            "default": False,
                        },
                    },
                    "required": ["code", "amount"],
                },
                "handler": self.create_coupon,
            },
            {
                "name": self._create_tool_name("update_coupon"),
                "description": f"Update an existing WooCommerce coupon in {self.project_id}. Can update discount amount, restrictions, and expiration.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "coupon_id": {"type": "integer", "description": "Coupon ID to update"},
                        "code": {"type": "string", "description": "Coupon code (e.g., 'SAVE20')"},
                        "discount_type": {
                            "type": "string",
                            "description": "Type of discount",
                            "enum": ["percent", "fixed_cart", "fixed_product"],
                        },
                        "amount": {"type": "string", "description": "Discount amount"},
                        "description": {
                            "type": "string",
                            "description": "Coupon description (internal note)",
                        },
                        "date_expires": {
                            "type": "string",
                            "description": "Expiration date in ISO 8601 format",
                        },
                        "minimum_amount": {"type": "string", "description": "Minimum order amount"},
                        "maximum_amount": {"type": "string", "description": "Maximum order amount"},
                        "usage_limit": {"type": "integer", "description": "Maximum number of uses"},
                        "usage_limit_per_user": {
                            "type": "integer",
                            "description": "Maximum uses per user",
                        },
                    },
                    "required": ["coupon_id"],
                },
                "handler": self.update_coupon,
            },
            {
                "name": self._create_tool_name("delete_coupon"),
                "description": f"Delete a WooCommerce coupon from {self.project_id}. Can force delete or move to trash.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "coupon_id": {"type": "integer", "description": "Coupon ID to delete"},
                        "force": {
                            "type": "boolean",
                            "description": "Force permanent delete (bypass trash)",
                            "default": False,
                        },
                    },
                    "required": ["coupon_id"],
                },
                "handler": self.delete_coupon,
            },
            # === PRODUCT ATTRIBUTES & VARIATIONS ===
            {
                "name": self._create_tool_name("list_product_attributes"),
                "description": f"List global product attributes from {self.project_id}. Returns attributes like Color, Size that can be used for variable products.",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.list_product_attributes,
            },
            {
                "name": self._create_tool_name("create_product_attribute"),
                "description": f"Create a new global product attribute in {self.project_id}. Used for creating attributes like Color, Size for variable products.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Attribute name (e.g., 'Color', 'Size')",
                        },
                        "slug": {
                            "type": "string",
                            "description": "Attribute slug (e.g., 'pa_color'). Auto-generated if not provided.",
                        },
                        "type": {
                            "type": "string",
                            "description": "Attribute type",
                            "enum": ["select"],
                            "default": "select",
                        },
                        "order_by": {
                            "type": "string",
                            "description": "Default sort order",
                            "enum": ["menu_order", "name", "name_num", "id"],
                            "default": "menu_order",
                        },
                        "has_archives": {
                            "type": "boolean",
                            "description": "Enable/disable attribute archives",
                            "default": False,
                        },
                    },
                    "required": ["name"],
                },
                "handler": self.create_product_attribute,
            },
            {
                "name": self._create_tool_name("list_product_variations"),
                "description": f"List variations of a variable product from {self.project_id}. Returns all size/color/etc variations for a product.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "integer",
                            "description": "Parent product ID (must be a variable product)",
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "Number of variations per page",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "default": 1,
                            "minimum": 1,
                        },
                    },
                    "required": ["product_id"],
                },
                "handler": self.list_product_variations,
            },
            {
                "name": self._create_tool_name("create_product_variation"),
                "description": f"Create a new variation for a variable product in {self.project_id}. Allows setting different prices and stock for each variant.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "integer",
                            "description": "Parent product ID (must be a variable product)",
                        },
                        "attributes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer", "description": "Attribute ID"},
                                    "name": {
                                        "type": "string",
                                        "description": "Attribute name (e.g., 'Color')",
                                    },
                                    "option": {
                                        "type": "string",
                                        "description": "Attribute value (e.g., 'Red')",
                                    },
                                },
                            },
                            "description": "Array of attributes for this variation (e.g., [{name: 'Size', option: 'M'}])",
                        },
                        "regular_price": {
                            "type": "string",
                            "description": "Regular price for this variation",
                        },
                        "sale_price": {
                            "type": "string",
                            "description": "Sale price for this variation",
                        },
                        "stock_quantity": {
                            "type": "integer",
                            "description": "Stock quantity for this variation",
                        },
                        "stock_status": {
                            "type": "string",
                            "description": "Stock status",
                            "enum": ["instock", "outofstock", "onbackorder"],
                            "default": "instock",
                        },
                        "manage_stock": {
                            "type": "boolean",
                            "description": "Enable stock management",
                            "default": False,
                        },
                        "sku": {"type": "string", "description": "SKU for this variation"},
                        "description": {"type": "string", "description": "Variation description"},
                        "image": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer", "description": "Image media ID"}
                            },
                            "description": "Variation image",
                        },
                    },
                    "required": ["product_id", "attributes"],
                },
                "handler": self.create_product_variation,
            },
            # === WOOCOMMERCE REPORTS & ANALYTICS ===
            {
                "name": self._create_tool_name("get_sales_report"),
                "description": f"Get sales report from {self.project_id}. Returns sales data with totals and date ranges.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "description": "Report period",
                            "enum": ["week", "month", "last_month", "year"],
                            "default": "week",
                        },
                        "date_min": {
                            "type": "string",
                            "description": "Start date for report (ISO 8601 format, e.g., '2024-01-01')",
                        },
                        "date_max": {
                            "type": "string",
                            "description": "End date for report (ISO 8601 format, e.g., '2024-12-31')",
                        },
                    },
                },
                "handler": self.get_sales_report,
            },
            {
                "name": self._create_tool_name("get_top_sellers"),
                "description": f"Get top selling products from {self.project_id}. Returns products with highest sales.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "description": "Report period",
                            "enum": ["week", "month", "last_month", "year"],
                            "default": "week",
                        },
                        "date_min": {
                            "type": "string",
                            "description": "Start date for report (ISO 8601 format)",
                        },
                        "date_max": {
                            "type": "string",
                            "description": "End date for report (ISO 8601 format)",
                        },
                    },
                },
                "handler": self.get_top_sellers,
            },
            {
                "name": self._create_tool_name("get_customer_report"),
                "description": f"Get customer statistics from {self.project_id}. Returns customer count and spending data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "description": "Report period",
                            "enum": ["week", "month", "last_month", "year"],
                            "default": "week",
                        },
                        "date_min": {
                            "type": "string",
                            "description": "Start date for report (ISO 8601 format)",
                        },
                        "date_max": {
                            "type": "string",
                            "description": "End date for report (ISO 8601 format)",
                        },
                    },
                },
                "handler": self.get_customer_report,
            },
            # === WOOCOMMERCE ORDERS ===
            {
                "name": self._create_tool_name("list_orders"),
                "description": f"List WooCommerce orders from {self.project_id}. Returns paginated order list with customer details, totals, and status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "Number of orders per page",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "default": 1,
                            "minimum": 1,
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by order status",
                            "enum": [
                                "any",
                                "pending",
                                "processing",
                                "on-hold",
                                "completed",
                                "cancelled",
                                "refunded",
                                "failed",
                                "trash",
                            ],
                        },
                        "customer": {"type": "integer", "description": "Filter by customer ID"},
                        "after": {
                            "type": "string",
                            "description": "Filter orders after this date (ISO 8601)",
                        },
                        "before": {
                            "type": "string",
                            "description": "Filter orders before this date (ISO 8601)",
                        },
                    },
                },
                "handler": self.list_orders,
            },
            {
                "name": self._create_tool_name("get_order"),
                "description": f"Get detailed information about a specific WooCommerce order from {self.project_id}. Returns full order details including line items, totals, billing, and shipping.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "integer", "description": "Order ID", "minimum": 1}
                    },
                    "required": ["order_id"],
                },
                "handler": self.get_order,
            },
            {
                "name": self._create_tool_name("update_order_status"),
                "description": f"Update WooCommerce order status in {self.project_id}. Change order status to pending, processing, completed, etc.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "integer", "description": "Order ID", "minimum": 1},
                        "status": {
                            "type": "string",
                            "description": "New order status",
                            "enum": [
                                "pending",
                                "processing",
                                "on-hold",
                                "completed",
                                "cancelled",
                                "refunded",
                                "failed",
                            ],
                        },
                    },
                    "required": ["order_id", "status"],
                },
                "handler": self.update_order_status,
            },
            {
                "name": self._create_tool_name("create_order"),
                "description": f"Create a new WooCommerce order in {self.project_id}. Supports line items, billing, shipping, and payment method.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "integer", "description": "Customer ID"},
                        "line_items": {
                            "type": "array",
                            "description": "Order line items",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "product_id": {"type": "integer"},
                                    "quantity": {"type": "integer"},
                                },
                            },
                        },
                        "billing": {"type": "object", "description": "Billing address"},
                        "shipping": {"type": "object", "description": "Shipping address"},
                        "payment_method": {"type": "string", "description": "Payment method ID"},
                        "status": {
                            "type": "string",
                            "description": "Order status",
                            "enum": ["pending", "processing", "on-hold", "completed"],
                            "default": "pending",
                        },
                    },
                },
                "handler": self.create_order,
            },
            {
                "name": self._create_tool_name("delete_order"),
                "description": f"Delete a WooCommerce order from {self.project_id}. Can force delete or move to trash.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "integer",
                            "description": "Order ID to delete",
                            "minimum": 1,
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force delete (true) or move to trash (false)",
                            "default": False,
                        },
                    },
                    "required": ["order_id"],
                },
                "handler": self.delete_order,
            },
            # === WOOCOMMERCE CUSTOMERS ===
            {
                "name": self._create_tool_name("list_customers"),
                "description": f"List WooCommerce customers from {self.project_id}. Returns paginated customer list with email, orders count, and total spent.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "Number of customers per page",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "default": 1,
                            "minimum": 1,
                        },
                        "search": {"type": "string", "description": "Search by name or email"},
                        "email": {"type": "string", "description": "Filter by specific email"},
                        "role": {
                            "type": "string",
                            "description": "Filter by role (customer, subscriber, etc.)",
                        },
                    },
                },
                "handler": self.list_customers,
            },
            {
                "name": self._create_tool_name("get_customer"),
                "description": f"Get detailed information about a specific WooCommerce customer from {self.project_id}. Returns customer details, billing, shipping, and order history.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "integer",
                            "description": "Customer ID",
                            "minimum": 1,
                        }
                    },
                    "required": ["customer_id"],
                },
                "handler": self.get_customer,
            },
            {
                "name": self._create_tool_name("create_customer"),
                "description": f"Create a new WooCommerce customer in {self.project_id}. Requires email, optionally includes name, billing, and shipping.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string", "description": "Customer email address"},
                        "first_name": {"type": "string", "description": "First name"},
                        "last_name": {"type": "string", "description": "Last name"},
                        "username": {
                            "type": "string",
                            "description": "Username (generated from email if not provided)",
                        },
                        "password": {
                            "type": "string",
                            "description": "Password (auto-generated if not provided)",
                        },
                        "billing": {"type": "object", "description": "Billing address"},
                        "shipping": {"type": "object", "description": "Shipping address"},
                    },
                    "required": ["email"],
                },
                "handler": self.create_customer,
            },
            {
                "name": self._create_tool_name("update_customer"),
                "description": f"Update an existing WooCommerce customer in {self.project_id}. Can update name, email, billing, shipping, and other fields.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "integer",
                            "description": "Customer ID to update",
                            "minimum": 1,
                        },
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "billing": {"type": "object"},
                        "shipping": {"type": "object"},
                    },
                    "required": ["customer_id"],
                },
                "handler": self.update_customer,
            },
            # === SEO (Rank Math / Yoast) ===
            {
                "name": self._create_tool_name("get_post_seo"),
                "description": f"Get SEO metadata for a WordPress post or page from {self.project_id}. Returns Rank Math or Yoast SEO fields including focus keyword, meta title, description, and social media settings. Requires SEO API Bridge plugin.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "integer",
                            "description": "Post or Page ID",
                            "minimum": 1,
                        }
                    },
                    "required": ["post_id"],
                },
                "handler": self.get_post_seo,
            },
            {
                "name": self._create_tool_name("update_post_seo"),
                "description": f"Update SEO metadata for a WordPress post or page in {self.project_id}. Supports both Rank Math and Yoast SEO fields. Automatically detects which plugin is active. Requires SEO API Bridge plugin.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "integer",
                            "description": "Post or Page ID to update",
                            "minimum": 1,
                        },
                        "focus_keyword": {
                            "type": "string",
                            "description": "Primary focus keyword for SEO",
                        },
                        "seo_title": {
                            "type": "string",
                            "description": "SEO meta title (appears in search results)",
                        },
                        "meta_description": {
                            "type": "string",
                            "description": "SEO meta description (appears in search results)",
                        },
                        "additional_keywords": {
                            "type": "string",
                            "description": "Additional keywords (comma-separated)",
                        },
                        "canonical_url": {
                            "type": "string",
                            "description": "Canonical URL for this content",
                        },
                        "robots": {
                            "type": "array",
                            "description": "Robots meta directives (e.g., ['noindex', 'nofollow'])",
                            "items": {"type": "string"},
                        },
                        "og_title": {
                            "type": "string",
                            "description": "Open Graph title for Facebook",
                        },
                        "og_description": {
                            "type": "string",
                            "description": "Open Graph description for Facebook",
                        },
                        "og_image": {
                            "type": "string",
                            "description": "Open Graph image URL for Facebook",
                        },
                        "twitter_title": {"type": "string", "description": "Twitter Card title"},
                        "twitter_description": {
                            "type": "string",
                            "description": "Twitter Card description",
                        },
                        "twitter_image": {
                            "type": "string",
                            "description": "Twitter Card image URL",
                        },
                    },
                    "required": ["post_id"],
                },
                "handler": self.update_post_seo,
            },
            {
                "name": self._create_tool_name("update_product_seo"),
                "description": f"Update SEO metadata for a WooCommerce product in {self.project_id}. Same as update_post_seo but specifically for products. Requires SEO API Bridge plugin.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "integer",
                            "description": "Product ID to update",
                            "minimum": 1,
                        },
                        "focus_keyword": {
                            "type": "string",
                            "description": "Primary focus keyword for SEO",
                        },
                        "seo_title": {
                            "type": "string",
                            "description": "SEO meta title (appears in search results)",
                        },
                        "meta_description": {
                            "type": "string",
                            "description": "SEO meta description (appears in search results)",
                        },
                        "additional_keywords": {
                            "type": "string",
                            "description": "Additional keywords (comma-separated)",
                        },
                        "canonical_url": {
                            "type": "string",
                            "description": "Canonical URL for this product",
                        },
                        "og_title": {
                            "type": "string",
                            "description": "Open Graph title for Facebook",
                        },
                        "og_description": {
                            "type": "string",
                            "description": "Open Graph description for Facebook",
                        },
                        "og_image": {
                            "type": "string",
                            "description": "Open Graph image URL for Facebook",
                        },
                    },
                    "required": ["product_id"],
                },
                "handler": self.update_product_seo,
            },
            # === WP-CLI TOOLS (Phase 5.1 + 5.2) ===
            # Note: Only available if container is configured
            *(
                [
                    # Phase 5.1: Cache Management (4 tools)
                    {
                        "name": self._create_tool_name("wp_cache_flush"),
                        "description": f"Flush WordPress object cache for {self.project_id} via WP-CLI. Clears all cached objects from Redis, Memcached, or file cache. Safe to run anytime.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_cache_flush,
                    },
                    {
                        "name": self._create_tool_name("wp_cache_type"),
                        "description": f"Get the object cache type for {self.project_id} via WP-CLI. Shows which caching backend is active (Redis, Memcached, file-based).",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_cache_type,
                    },
                    {
                        "name": self._create_tool_name("wp_transient_delete_all"),
                        "description": f"Delete all expired transients for {self.project_id} via WP-CLI. Removes expired temporary cached data from database, improving performance.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_transient_delete_all,
                    },
                    {
                        "name": self._create_tool_name("wp_transient_list"),
                        "description": f"List all transients for {self.project_id} via WP-CLI. Shows all transient keys with expiration times for debugging.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_transient_list,
                    },
                    # Phase 5.2: Database Operations (3 tools)
                    {
                        "name": self._create_tool_name("wp_db_check"),
                        "description": f"Check WordPress database health for {self.project_id} via WP-CLI. Runs database integrity checks to ensure tables are healthy. Safe operation - read-only.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_db_check,
                    },
                    {
                        "name": self._create_tool_name("wp_db_optimize"),
                        "description": f"Optimize WordPress database tables for {self.project_id} via WP-CLI. Runs OPTIMIZE TABLE on all tables to reclaim space and improve performance. Safe operation - non-destructive.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_db_optimize,
                    },
                    {
                        "name": self._create_tool_name("wp_db_export"),
                        "description": f"Export WordPress database for {self.project_id} via WP-CLI. Creates a backup in /tmp directory with timestamp. Safe - exports only to /tmp for security.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_db_export,
                    },
                    # Phase 5.2: Plugin/Theme Info (4 tools)
                    {
                        "name": self._create_tool_name("wp_plugin_list_detailed"),
                        "description": f"List all WordPress plugins for {self.project_id} via WP-CLI. Returns paginated plugin list with names, versions, status (active/inactive), and available updates. Useful for inventory management and update planning.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_plugin_list_detailed,
                    },
                    {
                        "name": self._create_tool_name("wp_theme_list_detailed"),
                        "description": f"List all WordPress themes for {self.project_id} via WP-CLI. Returns theme list with names, versions, status, and identifies the active theme. Useful for theme management and updates.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_theme_list_detailed,
                    },
                    {
                        "name": self._create_tool_name("wp_plugin_verify_checksums"),
                        "description": f"Verify plugin file integrity for {self.project_id} via WP-CLI. Checks all plugins against WordPress.org checksums to detect tampering or corruption. Important security tool for detecting malware. Only works for plugins from WordPress.org - premium/custom plugins are skipped.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_plugin_verify_checksums,
                    },
                    {
                        "name": self._create_tool_name("wp_core_verify_checksums"),
                        "description": f"Verify WordPress core files for {self.project_id} via WP-CLI. Checks core files for tampering, corruption, or unauthorized modifications. Critical security tool for ensuring WordPress integrity.",
                        "inputSchema": {"type": "object", "properties": {}},
                        "handler": self.wp_core_verify_checksums,
                    },
                    # Phase 5.3: Search & Replace + Update Tools
                    {
                        "name": self._create_tool_name("wp_search_replace_dry_run"),
                        "description": f"Search and replace in database for {self.project_id} via WP-CLI (DRY RUN ONLY). Previews what would be changed - NEVER makes actual changes. Safe preview tool for database migrations.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "old_string": {
                                    "type": "string",
                                    "description": "String to search for (e.g., 'old-domain.com')",
                                },
                                "new_string": {
                                    "type": "string",
                                    "description": "String to replace with (e.g., 'new-domain.com')",
                                },
                                "tables": {
                                    "anyOf": [
                                        {"type": "array", "items": {"type": "string"}},
                                        {"type": "null"},
                                    ],
                                    "description": "Optional list of specific tables to search (default: all tables)",
                                },
                            },
                            "required": ["old_string", "new_string"],
                        },
                        "handler": self.wp_search_replace_dry_run,
                    },
                    {
                        "name": self._create_tool_name("wp_plugin_update"),
                        "description": f"Update WordPress plugin(s) for {self.project_id} via WP-CLI. Default: DRY RUN mode (shows available updates only). Set dry_run=false to apply updates. ⚠️ WARNING: Always backup before updating. Check compatibility for major updates.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "plugin_name": {
                                    "type": "string",
                                    "description": "Plugin slug (e.g., 'woocommerce') or 'all' for all plugins",
                                },
                                "dry_run": {
                                    "anyOf": [{"type": "boolean"}, {"type": "null"}],
                                    "description": "If true, only show available updates without applying (default: true)",
                                },
                            },
                            "required": ["plugin_name"],
                        },
                        "handler": self.wp_plugin_update,
                    },
                    {
                        "name": self._create_tool_name("wp_theme_update"),
                        "description": f"Update WordPress theme(s) for {self.project_id} via WP-CLI. Default: DRY RUN mode (shows available updates only). Set dry_run=false to apply updates. ⚠️ WARNING: Updating active theme can break site appearance. Always backup and test first.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "theme_name": {
                                    "type": "string",
                                    "description": "Theme slug (e.g., 'storefront') or 'all' for all themes",
                                },
                                "dry_run": {
                                    "anyOf": [{"type": "boolean"}, {"type": "null"}],
                                    "description": "If true, only show available updates without applying (default: true)",
                                },
                            },
                            "required": ["theme_name"],
                        },
                        "handler": self.wp_theme_update,
                    },
                    {
                        "name": self._create_tool_name("wp_core_update"),
                        "description": f"Update WordPress core for {self.project_id} via WP-CLI. Default: DRY RUN mode (shows available updates only). Set dry_run=false to apply updates. ⚠️ CRITICAL: Core updates require full backup. Major updates may have breaking changes. Test on staging first!",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "version": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}],
                                    "description": "Specific version to update to (e.g., '6.4.3'), or null for latest",
                                },
                                "dry_run": {
                                    "anyOf": [{"type": "boolean"}, {"type": "null"}],
                                    "description": "If true, only show available updates without applying (default: true)",
                                },
                            },
                            "required": [],
                        },
                        "handler": self.wp_core_update,
                    },
                ]
                if self.wp_cli
                else []
            ),
            # === PHASE 6.1: NAVIGATION MENUS ===
            {
                "name": self._create_tool_name("list_menus"),
                "description": f"List all WordPress navigation menus from {self.project_id}. Returns menu list with IDs, names, slugs, assigned locations, and item counts.",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
                "handler": self.list_menus,
            },
            {
                "name": self._create_tool_name("get_menu"),
                "description": f"Get detailed information about a specific WordPress menu from {self.project_id}. Returns menu details and all menu items with hierarchy.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"menu_id": {"type": "integer", "description": "Menu ID"}},
                    "required": ["menu_id"],
                },
                "handler": self.get_menu,
            },
            {
                "name": self._create_tool_name("create_menu"),
                "description": f"Create a new navigation menu in {self.project_id}. Supports menu name, custom slug, and theme location assignment.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Menu name"},
                        "slug": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "Menu slug (auto-generated if not provided)",
                        },
                        "locations": {
                            "anyOf": [
                                {"type": "array", "items": {"type": "string"}},
                                {"type": "null"},
                            ],
                            "description": "Theme locations to assign menu to (e.g., ['primary', 'footer'])",
                        },
                    },
                    "required": ["name"],
                },
                "handler": self.create_menu,
            },
            {
                "name": self._create_tool_name("list_menu_items"),
                "description": f"List all items in a specific menu from {self.project_id}. Returns menu items with hierarchy, type, and link information.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"menu_id": {"type": "integer", "description": "Menu ID"}},
                    "required": ["menu_id"],
                },
                "handler": self.list_menu_items,
            },
            {
                "name": self._create_tool_name("create_menu_item"),
                "description": f"Add a new item to a menu in {self.project_id}. Supports linking to posts, pages, categories, or custom URLs. Can create sub-menu items with parent parameter.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "menu_id": {"type": "integer", "description": "Menu ID to add item to"},
                        "title": {
                            "type": "string",
                            "description": "Item title/label displayed in menu",
                        },
                        "type": {
                            "type": "string",
                            "description": "Item type: 'post_type' (link to post/page), 'taxonomy' (link to category/tag), 'custom' (custom URL)",
                        },
                        "object_id": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "ID of linked post or term (required for post_type/taxonomy types)",
                        },
                        "url": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "Custom URL (required for type=custom)",
                        },
                        "parent": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "Parent item ID for creating sub-menu items",
                        },
                    },
                    "required": ["menu_id", "title", "type"],
                },
                "handler": self.create_menu_item,
            },
            {
                "name": self._create_tool_name("update_menu_item"),
                "description": f"Update an existing menu item in {self.project_id}. Can update title, URL, parent (for hierarchy), and menu order (position).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer", "description": "Menu item ID to update"},
                        "title": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "New item title",
                        },
                        "url": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "New URL",
                        },
                        "parent": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "New parent item ID (for changing hierarchy)",
                        },
                        "menu_order": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "Position in menu (for reordering)",
                        },
                    },
                    "required": ["item_id"],
                },
                "handler": self.update_menu_item,
            },
            # === PHASE 6.2: CUSTOM POST TYPES ===
            {
                "name": self._create_tool_name("list_post_types"),
                "description": f"List all registered post types in {self.project_id}. Returns both built-in types (post, page) and custom post types (portfolio, testimonials, etc.) with their capabilities and supported features.",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
                "handler": self.list_post_types,
            },
            {
                "name": self._create_tool_name("get_post_type_info"),
                "description": f"Get detailed information about a specific post type in {self.project_id}. Returns post type configuration, capabilities, taxonomies, and REST API settings.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_type": {
                            "type": "string",
                            "description": "Post type slug (e.g., 'portfolio', 'post', 'page')",
                        }
                    },
                    "required": ["post_type"],
                },
                "handler": self.get_post_type_info,
            },
            {
                "name": self._create_tool_name("list_custom_posts"),
                "description": f"List posts of a specific custom post type from {self.project_id}. Supports pagination and status filtering. Works with any registered post type including custom ones.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_type": {
                            "type": "string",
                            "description": "Post type slug (e.g., 'portfolio', 'testimonials')",
                        },
                        "per_page": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "Number of posts per page (default: 10)",
                        },
                        "page": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "Page number (default: 1)",
                        },
                        "status": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "Filter by status: publish, draft, pending, etc. (default: any)",
                        },
                    },
                    "required": ["post_type"],
                },
                "handler": self.list_custom_posts,
            },
            {
                "name": self._create_tool_name("create_custom_post"),
                "description": f"Create a new post of a custom post type in {self.project_id}. Supports HTML content, custom fields, and meta data. Post type must be registered and REST-enabled.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_type": {
                            "type": "string",
                            "description": "Post type slug (e.g., 'portfolio')",
                        },
                        "title": {"type": "string", "description": "Post title"},
                        "content": {"type": "string", "description": "Post content (HTML allowed)"},
                        "status": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "Post status: draft, publish, pending, etc. (default: draft)",
                        },
                        "meta": {
                            "anyOf": [
                                {"type": "object", "additionalProperties": True},
                                {"type": "null"},
                            ],
                            "description": "Custom fields/meta data as key-value pairs",
                        },
                    },
                    "required": ["post_type", "title", "content"],
                },
                "handler": self.create_custom_post,
            },
            # === PHASE 6.3: CUSTOM TAXONOMIES ===
            {
                "name": self._create_tool_name("list_taxonomies"),
                "description": f"List all registered taxonomies in {self.project_id}. Returns both built-in taxonomies (category, post_tag) and custom taxonomies with their configuration and assigned post types.",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
                "handler": self.list_taxonomies,
            },
            {
                "name": self._create_tool_name("list_taxonomy_terms"),
                "description": f"List terms of a specific taxonomy from {self.project_id}. Supports pagination, filtering by parent term, and hiding empty terms. Works with any registered taxonomy.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "taxonomy": {
                            "type": "string",
                            "description": "Taxonomy slug (e.g., 'category', 'post_tag', 'product_cat')",
                        },
                        "per_page": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "Number of terms per page (default: 100)",
                        },
                        "page": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "Page number (default: 1)",
                        },
                        "hide_empty": {
                            "anyOf": [{"type": "boolean"}, {"type": "null"}],
                            "description": "Hide terms with no posts (default: false)",
                        },
                        "parent": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "Filter by parent term ID (for hierarchical taxonomies)",
                        },
                    },
                    "required": ["taxonomy"],
                },
                "handler": self.list_taxonomy_terms,
            },
            {
                "name": self._create_tool_name("create_taxonomy_term"),
                "description": f"Create a new term in a taxonomy for {self.project_id}. Supports hierarchical taxonomies with parent terms. Term slug is auto-generated from name if not provided.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "taxonomy": {
                            "type": "string",
                            "description": "Taxonomy slug (e.g., 'category', 'product_cat')",
                        },
                        "name": {"type": "string", "description": "Term name"},
                        "description": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "Term description",
                        },
                        "parent": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "description": "Parent term ID for hierarchical taxonomies (e.g., subcategories)",
                        },
                    },
                    "required": ["taxonomy", "name"],
                },
                "handler": self.create_taxonomy_term,
            },
        ]

    # === IMPLEMENTATION ===

    async def list_posts(
        self, per_page: int = 10, page: int = 1, status: str = "any", search: str | None = None
    ) -> str:
        """List WordPress posts."""
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "status": status,
                "_embed": "true",  # Include author and featured image
            }
            if search:
                params["search"] = search

            posts = await self._make_request("GET", "posts", params=params)

            # Format response
            result = {
                "total": len(posts),
                "page": page,
                "per_page": per_page,
                "posts": [
                    {
                        "id": post["id"],
                        "title": post["title"]["rendered"],
                        "excerpt": post["excerpt"]["rendered"][:200],
                        "status": post["status"],
                        "date": post["date"],
                        "author": post.get("_embedded", {})
                        .get("author", [{}])[0]
                        .get("name", "Unknown"),
                        "link": post["link"],
                    }
                    for post in posts
                ],
            }

            return self._format_success_response(result, "list_posts")
        except Exception as e:
            return self._format_error_response(e, "list_posts")

    async def get_post(self, post_id: int) -> str:
        """Get a specific post."""
        try:
            post = await self._make_request("GET", f"posts/{post_id}", params={"_embed": "true"})

            result = {
                "id": post["id"],
                "title": post["title"]["rendered"],
                "content": post["content"]["rendered"],
                "excerpt": post["excerpt"]["rendered"],
                "status": post["status"],
                "date": post["date"],
                "modified": post["modified"],
                "author": post.get("_embedded", {}).get("author", [{}])[0].get("name", "Unknown"),
                "categories": post.get("categories", []),
                "tags": post.get("tags", []),
                "link": post["link"],
            }

            return self._format_success_response(result, "get_post")
        except Exception as e:
            return self._format_error_response(e, "get_post")

    async def create_post(
        self,
        title: str,
        content: str,
        status: str = "draft",
        slug: str | None = None,
        excerpt: str | None = None,
        categories: list[int] | None = None,
        tags: list[int] | None = None,
        featured_media: int | None = None,
    ) -> str:
        """Create a new post with optional slug."""
        try:
            data = {"title": title, "content": content, "status": status}
            if slug:
                data["slug"] = slug
            if excerpt:
                data["excerpt"] = excerpt
            if categories:
                data["categories"] = categories
            if tags:
                data["tags"] = tags
            if featured_media:
                data["featured_media"] = featured_media

            post = await self._make_request("POST", "posts", json_data=data)

            result = {
                "id": post["id"],
                "title": post["title"]["rendered"],
                "status": post["status"],
                "link": post["link"],
                "message": f"Post created successfully with ID {post['id']}",
            }

            return self._format_success_response(result, "create_post")
        except Exception as e:
            return self._format_error_response(e, "create_post")

    async def update_post(self, post_id: int, **kwargs) -> str:
        """Update an existing post."""
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}

            post = await self._make_request("POST", f"posts/{post_id}", json_data=data)

            result = {
                "id": post["id"],
                "title": post["title"]["rendered"],
                "status": post["status"],
                "link": post["link"],
                "message": f"Post {post_id} updated successfully",
            }

            return self._format_success_response(result, "update_post")
        except Exception as e:
            return self._format_error_response(e, "update_post")

    async def delete_post(self, post_id: int, force: bool = False) -> str:
        """Delete a post."""
        try:
            params = {"force": "true" if force else "false"}
            await self._make_request("DELETE", f"posts/{post_id}", params=params)

            message = f"Post {post_id} {'permanently deleted' if force else 'moved to trash'}"
            return self._format_success_response({"message": message}, "delete_post")
        except Exception as e:
            return self._format_error_response(e, "delete_post")

    async def list_pages(self, per_page: int = 10, page: int = 1, status: str = "any") -> str:
        """List WordPress pages."""
        try:
            params = {"per_page": per_page, "page": page, "status": status}
            pages = await self._make_request("GET", "pages", params=params)

            result = {
                "total": len(pages),
                "pages": [
                    {
                        "id": p["id"],
                        "title": p["title"]["rendered"],
                        "status": p["status"],
                        "date": p["date"],
                        "link": p["link"],
                    }
                    for p in pages
                ],
            }

            return self._format_success_response(result, "list_pages")
        except Exception as e:
            return self._format_error_response(e, "list_pages")

    async def create_page(
        self,
        title: str,
        content: str,
        status: str = "draft",
        slug: str | None = None,
        parent: int | None = None,
    ) -> str:
        """Create a new page with optional slug and parent."""
        try:
            data = {"title": title, "content": content, "status": status}
            if slug:
                data["slug"] = slug
            if parent:
                data["parent"] = parent

            page = await self._make_request("POST", "pages", json_data=data)

            result = {
                "id": page["id"],
                "title": page["title"]["rendered"],
                "status": page["status"],
                "link": page["link"],
                "message": f"Page created successfully with ID {page['id']}",
            }

            return self._format_success_response(result, "create_page")
        except Exception as e:
            return self._format_error_response(e, "create_page")

    async def update_page(self, page_id: int, **kwargs) -> str:
        """Update an existing page."""
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}

            page = await self._make_request("POST", f"pages/{page_id}", json_data=data)

            result = {
                "id": page["id"],
                "title": page["title"]["rendered"],
                "status": page["status"],
                "link": page["link"],
                "message": f"Page {page_id} updated successfully",
            }

            return self._format_success_response(result, "update_page")
        except Exception as e:
            return self._format_error_response(e, "update_page")

    async def list_media(
        self, per_page: int = 20, page: int = 1, media_type: str | None = None
    ) -> str:
        """List media library items."""
        try:
            params = {"per_page": per_page, "page": page}
            if media_type:
                params["media_type"] = media_type

            media = await self._make_request("GET", "media", params=params)

            result = {
                "total": len(media),
                "media": [
                    {
                        "id": m["id"],
                        "title": m["title"]["rendered"],
                        "mime_type": m["mime_type"],
                        "url": m["source_url"],
                        "date": m["date"],
                    }
                    for m in media
                ],
            }

            return self._format_success_response(result, "list_media")
        except Exception as e:
            return self._format_error_response(e, "list_media")

    async def get_media(self, media_id: int) -> str:
        """Get specific media item."""
        try:
            media = await self._make_request("GET", f"media/{media_id}")

            result = {
                "id": media["id"],
                "title": media["title"]["rendered"],
                "mime_type": media["mime_type"],
                "url": media["source_url"],
                "alt_text": media.get("alt_text", ""),
                "caption": media.get("caption", {}).get("rendered", ""),
                "date": media["date"],
            }

            return self._format_success_response(result, "get_media")
        except Exception as e:
            return self._format_error_response(e, "get_media")

    async def list_users(
        self, per_page: int = 10, page: int = 1, roles: list[str] | None = None
    ) -> str:
        """List WordPress users."""
        try:
            params = {"per_page": per_page, "page": page}
            if roles:
                params["roles"] = ",".join(roles)

            users = await self._make_request("GET", "users", params=params)

            result = {
                "total": len(users),
                "users": [
                    {
                        "id": u["id"],
                        "name": u["name"],
                        "username": u["slug"],
                        "email": u.get("email", "N/A"),
                        "roles": u.get("roles", []),
                    }
                    for u in users
                ],
            }

            return self._format_success_response(result, "list_users")
        except Exception as e:
            return self._format_error_response(e, "list_users")

    async def get_current_user(self) -> str:
        """Get current authenticated user."""
        try:
            user = await self._make_request("GET", "users/me")

            result = {
                "id": user["id"],
                "name": user["name"],
                "username": user["slug"],
                "email": user.get("email", "N/A"),
                "roles": user.get("roles", []),
            }

            return self._format_success_response(result, "get_current_user")
        except Exception as e:
            return self._format_error_response(e, "get_current_user")

    async def list_plugins(self, status: str = "all") -> str:
        """List installed plugins."""
        try:
            endpoint = "plugins"
            if status != "all":
                endpoint += f"?status={status}"

            plugins = await self._make_request("GET", endpoint)

            result = {
                "total": len(plugins),
                "plugins": [
                    {
                        "plugin": p["plugin"],
                        "name": p["name"],
                        "version": p["version"],
                        "status": p["status"],
                        "description": p.get("description", {}).get("raw", "")[:100],
                    }
                    for p in plugins
                ],
            }

            return self._format_success_response(result, "list_plugins")
        except Exception as e:
            return self._format_error_response(e, "list_plugins")

    async def list_themes(self, status: str = "all") -> str:
        """List installed themes."""
        try:
            endpoint = "themes"
            if status != "all":
                endpoint += f"?status={status}"

            themes = await self._make_request("GET", endpoint)

            result = {
                "total": len(themes),
                "themes": [
                    {
                        "stylesheet": t["stylesheet"],
                        "name": t["name"]["rendered"],
                        "version": t["version"],
                        "status": t["status"],
                    }
                    for t in themes
                ],
            }

            return self._format_success_response(result, "list_themes")
        except Exception as e:
            return self._format_error_response(e, "list_themes")

    async def get_active_theme(self) -> str:
        """Get active theme."""
        try:
            themes = await self._make_request("GET", "themes?status=active")

            if themes:
                theme = themes[0]
                result = {
                    "stylesheet": theme["stylesheet"],
                    "name": theme["name"]["rendered"],
                    "version": theme["version"],
                    "author": theme.get("author", {}).get("raw", "Unknown"),
                }
            else:
                result = {"message": "No active theme found"}

            return self._format_success_response(result, "get_active_theme")
        except Exception as e:
            return self._format_error_response(e, "get_active_theme")

    async def get_settings(self) -> str:
        """Get site settings."""
        try:
            settings = await self._make_request("GET", "settings")

            result = {
                "title": settings.get("title", ""),
                "description": settings.get("description", ""),
                "url": settings.get("url", ""),
                "email": settings.get("email", ""),
                "timezone": settings.get("timezone_string", ""),
                "language": settings.get("language", ""),
            }

            return self._format_success_response(result, "get_settings")
        except Exception as e:
            return self._format_error_response(e, "get_settings")

    async def get_site_health(self) -> str:
        """Check site health."""
        try:
            health = await self.health_check()
            return self._format_success_response(health, "get_site_health")
        except Exception as e:
            return self._format_error_response(e, "get_site_health")

    # === MEDIA UPLOAD ===

    async def upload_media_from_url(
        self,
        url: str,
        title: str | None = None,
        alt_text: str | None = None,
        caption: str | None = None,
    ) -> str:
        """Upload media from URL (sideload)."""
        try:
            # Download file from URL
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                if response.status >= 400:
                    raise Exception(f"Failed to download from URL: {response.status}")

                file_content = await response.read()
                content_type = response.headers.get("Content-Type", "application/octet-stream")

                # Extract filename from URL
                filename = url.split("/")[-1].split("?")[0]
                if not filename:
                    filename = "downloaded_file"

            # Create FormData
            form = aiohttp.FormData()
            form.add_field("file", file_content, filename=filename, content_type=content_type)

            # Upload to WordPress
            upload_url = f"{self.api_base}/media"
            headers = {
                "Authorization": self.auth_header,
                "Content-Disposition": f'attachment; filename="{filename}"',
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(upload_url, data=form, headers=headers) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"Upload failed ({response.status}): {error_text}")

                    media = await response.json()

            # Update metadata if provided
            if title or alt_text or caption:
                update_data = {}
                if title:
                    update_data["title"] = title
                if alt_text:
                    update_data["alt_text"] = alt_text
                if caption:
                    update_data["caption"] = caption

                await self._make_request("POST", f"media/{media['id']}", json_data=update_data)

            result = {
                "id": media["id"],
                "title": media["title"]["rendered"],
                "url": media["source_url"],
                "mime_type": media["mime_type"],
                "message": f"Media uploaded from URL successfully with ID {media['id']}",
            }

            return self._format_success_response(result, "upload_media_from_url")
        except Exception as e:
            return self._format_error_response(e, "upload_media_from_url")

    async def update_media(self, media_id: int, **kwargs) -> str:
        """Update media metadata."""
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}

            media = await self._make_request("POST", f"media/{media_id}", json_data=data)

            result = {
                "id": media["id"],
                "title": media["title"]["rendered"],
                "alt_text": media.get("alt_text", ""),
                "caption": media.get("caption", {}).get("rendered", ""),
                "message": f"Media {media_id} updated successfully",
            }

            return self._format_success_response(result, "update_media")
        except Exception as e:
            return self._format_error_response(e, "update_media")

    async def delete_media(self, media_id: int, force: bool = False) -> str:
        """Delete media from library."""
        try:
            params = {"force": "true" if force else "false"}
            await self._make_request("DELETE", f"media/{media_id}", params=params)

            message = f"Media {media_id} {'permanently deleted' if force else 'moved to trash'}"
            return self._format_success_response({"message": message}, "delete_media")
        except Exception as e:
            return self._format_error_response(e, "delete_media")

    # === COMMENTS MANAGEMENT ===

    async def list_comments(
        self, per_page: int = 10, page: int = 1, post: int | None = None, status: str = "approve"
    ) -> str:
        """List comments."""
        try:
            params = {"per_page": per_page, "page": page, "status": status}
            if post:
                params["post"] = post

            comments = await self._make_request("GET", "comments", params=params)

            result = {
                "total": len(comments),
                "page": page,
                "comments": [
                    {
                        "id": c["id"],
                        "post_id": c["post"],
                        "author_name": c["author_name"],
                        "author_email": c.get("author_email", ""),
                        "content": c["content"]["rendered"][:200],
                        "status": c["status"],
                        "date": c["date"],
                    }
                    for c in comments
                ],
            }

            return self._format_success_response(result, "list_comments")
        except Exception as e:
            return self._format_error_response(e, "list_comments")

    async def get_comment(self, comment_id: int) -> str:
        """Get a specific comment."""
        try:
            comment = await self._make_request("GET", f"comments/{comment_id}")

            result = {
                "id": comment["id"],
                "post_id": comment["post"],
                "author_name": comment["author_name"],
                "author_email": comment.get("author_email", ""),
                "content": comment["content"]["rendered"],
                "status": comment["status"],
                "date": comment["date"],
                "link": comment["link"],
            }

            return self._format_success_response(result, "get_comment")
        except Exception as e:
            return self._format_error_response(e, "get_comment")

    async def create_comment(
        self,
        post_id: int,
        content: str,
        author_name: str | None = None,
        author_email: str | None = None,
        status: str = "hold",
    ) -> str:
        """Create a new comment."""
        try:
            data = {"post": post_id, "content": content, "status": status}
            if author_name:
                data["author_name"] = author_name
            if author_email:
                data["author_email"] = author_email

            comment = await self._make_request("POST", "comments", json_data=data)

            result = {
                "id": comment["id"],
                "post_id": comment["post"],
                "content": comment["content"]["rendered"],
                "status": comment["status"],
                "message": f"Comment created successfully with ID {comment['id']}",
            }

            return self._format_success_response(result, "create_comment")
        except Exception as e:
            return self._format_error_response(e, "create_comment")

    async def update_comment(self, comment_id: int, **kwargs) -> str:
        """Update an existing comment."""
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}

            comment = await self._make_request("POST", f"comments/{comment_id}", json_data=data)

            result = {
                "id": comment["id"],
                "content": comment["content"]["rendered"],
                "status": comment["status"],
                "message": f"Comment {comment_id} updated successfully",
            }

            return self._format_success_response(result, "update_comment")
        except Exception as e:
            return self._format_error_response(e, "update_comment")

    async def delete_comment(self, comment_id: int, force: bool = False) -> str:
        """Delete a comment."""
        try:
            params = {"force": "true" if force else "false"}
            await self._make_request("DELETE", f"comments/{comment_id}", params=params)

            message = f"Comment {comment_id} {'permanently deleted' if force else 'moved to trash'}"
            return self._format_success_response({"message": message}, "delete_comment")
        except Exception as e:
            return self._format_error_response(e, "delete_comment")

    # === CATEGORIES MANAGEMENT ===

    async def list_categories(
        self, per_page: int = 100, page: int = 1, hide_empty: bool = False
    ) -> str:
        """List post categories."""
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",  # WordPress expects string
            }

            categories = await self._make_request("GET", "categories", params=params)

            result = {
                "total": len(categories),
                "categories": [
                    {
                        "id": cat["id"],
                        "name": cat["name"],
                        "slug": cat["slug"],
                        "description": cat.get("description", ""),
                        "count": cat.get("count", 0),
                        "parent": cat.get("parent", 0),
                    }
                    for cat in categories
                ],
            }

            return self._format_success_response(result, "list_categories")
        except Exception as e:
            return self._format_error_response(e, "list_categories")

    async def create_category(
        self, name: str, description: str | None = None, parent: int | None = None
    ) -> str:
        """Create a new category."""
        try:
            data = {"name": name}
            if description:
                data["description"] = description
            if parent:
                data["parent"] = parent

            category = await self._make_request("POST", "categories", json_data=data)

            result = {
                "id": category["id"],
                "name": category["name"],
                "slug": category["slug"],
                "message": f"Category '{name}' created successfully with ID {category['id']}",
            }

            return self._format_success_response(result, "create_category")
        except Exception as e:
            return self._format_error_response(e, "create_category")

    async def update_category(self, category_id: int, **kwargs) -> str:
        """Update an existing category."""
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}

            category = await self._make_request("POST", f"categories/{category_id}", json_data=data)

            result = {
                "id": category["id"],
                "name": category["name"],
                "slug": category["slug"],
                "message": f"Category {category_id} updated successfully",
            }

            return self._format_success_response(result, "update_category")
        except Exception as e:
            return self._format_error_response(e, "update_category")

    async def delete_category(self, category_id: int, force: bool = False) -> str:
        """Delete a category."""
        try:
            params = {"force": "true" if force else "false"}
            await self._make_request("DELETE", f"categories/{category_id}", params=params)

            message = f"Category {category_id} deleted successfully"
            return self._format_success_response({"message": message}, "delete_category")
        except Exception as e:
            return self._format_error_response(e, "delete_category")

    # === TAGS MANAGEMENT ===

    async def list_tags(self, per_page: int = 100, page: int = 1, hide_empty: bool = False) -> str:
        """List post tags."""
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",  # WordPress expects string
            }

            tags = await self._make_request("GET", "tags", params=params)

            result = {
                "total": len(tags),
                "tags": [
                    {
                        "id": tag["id"],
                        "name": tag["name"],
                        "slug": tag["slug"],
                        "description": tag.get("description", ""),
                        "count": tag.get("count", 0),
                    }
                    for tag in tags
                ],
            }

            return self._format_success_response(result, "list_tags")
        except Exception as e:
            return self._format_error_response(e, "list_tags")

    async def create_tag(self, name: str, description: str | None = None) -> str:
        """Create a new tag."""
        try:
            data = {"name": name}
            if description:
                data["description"] = description

            tag = await self._make_request("POST", "tags", json_data=data)

            result = {
                "id": tag["id"],
                "name": tag["name"],
                "slug": tag["slug"],
                "message": f"Tag '{name}' created successfully with ID {tag['id']}",
            }

            return self._format_success_response(result, "create_tag")
        except Exception as e:
            return self._format_error_response(e, "create_tag")

    async def update_tag(self, tag_id: int, **kwargs) -> str:
        """Update an existing tag."""
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}

            tag = await self._make_request("POST", f"tags/{tag_id}", json_data=data)

            result = {
                "id": tag["id"],
                "name": tag["name"],
                "slug": tag["slug"],
                "message": f"Tag {tag_id} updated successfully",
            }

            return self._format_success_response(result, "update_tag")
        except Exception as e:
            return self._format_error_response(e, "update_tag")

    async def delete_tag(self, tag_id: int, force: bool = False) -> str:
        """Delete a tag."""
        try:
            params = {"force": "true" if force else "false"}
            await self._make_request("DELETE", f"tags/{tag_id}", params=params)

            message = f"Tag {tag_id} deleted successfully"
            return self._format_success_response({"message": message}, "delete_tag")
        except Exception as e:
            return self._format_error_response(e, "delete_tag")

    # ========================================
    # WooCommerce Methods
    # ========================================

    async def check_woocommerce(self) -> dict[str, Any]:
        """Check if WooCommerce is installed and active."""
        try:
            # Try to access WooCommerce system status endpoint
            url = f"{self.wc_api_base}/system_status"
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers={"Authorization": self.auth_header}) as response,
            ):
                if response.status == 200:
                    data = await response.json()
                    return {
                        "active": True,
                        "version": data.get("environment", {}).get("version", "Unknown"),
                    }
                else:
                    return {"active": False, "message": "WooCommerce not accessible"}
        except Exception as e:
            return {"active": False, "message": f"WooCommerce check failed: {str(e)}"}

    async def check_seo_plugins(self) -> dict[str, Any]:
        """Check if Rank Math or Yoast SEO is installed and SEO API Bridge is active."""
        try:
            # First, try to use the new health check endpoint (v1.1.0+)
            try:
                status_result = await self._make_request(
                    "GET", "seo-api-bridge/v1/status", use_custom_namespace=True
                )

                if status_result and isinstance(status_result, dict):
                    # Successfully got status from dedicated endpoint
                    rank_math_info = status_result.get("seo_plugins", {}).get("rank_math", {})
                    yoast_info = status_result.get("seo_plugins", {}).get("yoast", {})

                    return {
                        "rank_math": {
                            "active": rank_math_info.get("active", False),
                            "version": rank_math_info.get("version"),
                        },
                        "yoast": {
                            "active": yoast_info.get("active", False),
                            "version": yoast_info.get("version"),
                        },
                        "api_bridge_active": True,
                        "api_bridge_version": status_result.get("version"),
                        "message": status_result.get("message", "SEO API Bridge is active"),
                    }
            except Exception:
                # Health check endpoint not available, fall back to old method
                pass

            # Fallback: Try to check posts for SEO meta fields
            result = await self._make_request("GET", "posts", params={"per_page": 1})

            # If no posts, try products
            if not result or (isinstance(result, list) and len(result) == 0):
                result = await self._make_request("GET", "products", params={"per_page": 1})

                if not result or (isinstance(result, list) and len(result) == 0):
                    return {
                        "rank_math": {"active": False},
                        "yoast": {"active": False},
                        "api_bridge_active": False,
                        "message": "No posts or products available to check SEO plugin status. Please install SEO API Bridge v1.1.0+ or create content with SEO metadata.",
                    }

            # Check if meta fields are present (indicates SEO API Bridge is active)
            first_item = result[0] if isinstance(result, list) and len(result) > 0 else {}
            meta = first_item.get("meta", {})

            # Check for Rank Math fields
            rank_math_active = any(
                key in meta
                for key in [
                    "rank_math_focus_keyword",
                    "rank_math_seo_title",
                    "rank_math_description",
                ]
            )

            # Check for Yoast SEO fields
            yoast_active = any(
                key in meta
                for key in ["_yoast_wpseo_focuskw", "_yoast_wpseo_title", "_yoast_wpseo_metadesc"]
            )

            api_bridge_active = rank_math_active or yoast_active

            return {
                "rank_math": {"active": rank_math_active},
                "yoast": {"active": yoast_active},
                "api_bridge_active": api_bridge_active,
                "message": (
                    "SEO API Bridge required. Please install and activate the plugin, then upgrade to v1.1.0+ for better detection."
                    if not api_bridge_active
                    else "SEO fields accessible via meta (legacy detection)"
                ),
            }
        except Exception as e:
            return {
                "rank_math": {"active": False},
                "yoast": {"active": False},
                "api_bridge_active": False,
                "message": f"SEO plugin check failed: {str(e)}",
            }

    # === PRODUCTS ===

    async def list_products(
        self,
        per_page: int = 10,
        page: int = 1,
        status: str = "any",
        category: int | None = None,
        stock_status: str | None = None,
        search: str | None = None,
    ) -> str:
        """List WooCommerce products."""
        try:
            # Build query parameters
            params = {"per_page": per_page, "page": page, "status": status}

            # Add optional filters
            if category is not None:
                params["category"] = category
            if stock_status:
                params["stock_status"] = stock_status
            if search:
                params["search"] = search

            # Make request to WooCommerce API
            url = f"{self.wc_api_base}/products"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                products = await response.json()

            # Format response
            result = {
                "total": len(products),
                "page": page,
                "per_page": per_page,
                "products": [
                    {
                        "id": p["id"],
                        "name": p["name"],
                        "slug": p["slug"],
                        "type": p["type"],
                        "status": p["status"],
                        "price": p["price"],
                        "regular_price": p["regular_price"],
                        "sale_price": p.get("sale_price", ""),
                        "stock_status": p["stock_status"],
                        "stock_quantity": p.get("stock_quantity"),
                        "categories": [
                            {"id": cat["id"], "name": cat["name"]}
                            for cat in p.get("categories", [])
                        ],
                        "images": [
                            {"id": img["id"], "src": img["src"], "alt": img.get("alt", "")}
                            for img in p.get("images", [])[:1]  # Just first image
                        ],
                        "permalink": p["permalink"],
                    }
                    for p in products
                ],
            }

            return self._format_success_response(result, "list_products")
        except Exception as e:
            return self._format_error_response(e, "list_products")

    async def get_product(self, product_id: int) -> str:
        """Get detailed information about a specific product."""
        try:
            url = f"{self.wc_api_base}/products/{product_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers={"Authorization": self.auth_header}) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                product = await response.json()

            result = {
                "id": product["id"],
                "name": product["name"],
                "slug": product["slug"],
                "type": product["type"],
                "status": product["status"],
                "description": product.get("description", ""),
                "short_description": product.get("short_description", ""),
                "price": product["price"],
                "regular_price": product["regular_price"],
                "sale_price": product.get("sale_price", ""),
                "stock_status": product["stock_status"],
                "stock_quantity": product.get("stock_quantity"),
                "manage_stock": product.get("manage_stock", False),
                "categories": [
                    {"id": cat["id"], "name": cat["name"], "slug": cat["slug"]}
                    for cat in product.get("categories", [])
                ],
                "tags": [
                    {"id": tag["id"], "name": tag["name"], "slug": tag["slug"]}
                    for tag in product.get("tags", [])
                ],
                "images": [
                    {"id": img["id"], "src": img["src"], "alt": img.get("alt", "")}
                    for img in product.get("images", [])
                ],
                "permalink": product["permalink"],
            }

            return self._format_success_response(result, "get_product")
        except Exception as e:
            return self._format_error_response(e, "get_product")

    async def create_product(
        self,
        name: str,
        type: str = "simple",
        regular_price: str | None = None,
        sale_price: str | None = None,
        description: str | None = None,
        short_description: str | None = None,
        status: str = "draft",
        categories: list[int] | None = None,
        tags: list[int] | None = None,
        stock_quantity: int | None = None,
        manage_stock: bool = False,
        stock_status: str = "instock",
    ) -> str:
        """Create a new WooCommerce product."""
        try:
            # Build product data
            data = {
                "name": name,
                "type": type,
                "status": status,
                "stock_status": stock_status,
                "manage_stock": manage_stock,
            }

            if regular_price:
                data["regular_price"] = regular_price
            if sale_price:
                data["sale_price"] = sale_price
            if description:
                data["description"] = description
            if short_description:
                data["short_description"] = short_description
            if categories:
                data["categories"] = [{"id": cat_id} for cat_id in categories]
            if tags:
                data["tags"] = [{"id": tag_id} for tag_id in tags]
            if stock_quantity is not None and manage_stock:
                data["stock_quantity"] = stock_quantity

            # Make request to WooCommerce API
            url = f"{self.wc_api_base}/products"
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                product = await response.json()

            result = {
                "id": product["id"],
                "name": product["name"],
                "type": product["type"],
                "status": product["status"],
                "price": product.get("price", ""),
                "permalink": product["permalink"],
                "message": f"Product '{name}' created successfully with ID {product['id']}",
            }

            return self._format_success_response(result, "create_product")
        except Exception as e:
            return self._format_error_response(e, "create_product")

    async def update_product(self, product_id: int, **kwargs) -> str:
        """Update an existing WooCommerce product."""
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}

            # Make request to WooCommerce API
            url = f"{self.wc_api_base}/products/{product_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.put(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                product = await response.json()

            result = {
                "id": product["id"],
                "name": product["name"],
                "status": product["status"],
                "price": product.get("price", ""),
                "message": f"Product {product_id} updated successfully",
            }

            return self._format_success_response(result, "update_product")
        except Exception as e:
            return self._format_error_response(e, "update_product")

    async def delete_product(self, product_id: int, force: bool = False) -> str:
        """Delete a WooCommerce product."""
        try:
            params = {"force": "true" if force else "false"}

            url = f"{self.wc_api_base}/products/{product_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.delete(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                await response.json()

            message = f"Product {product_id} {'permanently deleted' if force else 'moved to trash'}"
            return self._format_success_response({"message": message}, "delete_product")
        except Exception as e:
            return self._format_error_response(e, "delete_product")

    # === PRODUCT CATEGORIES ===

    async def list_product_categories(
        self, per_page: int = 10, page: int = 1, hide_empty: bool = False
    ) -> str:
        """List WooCommerce product categories."""
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",
            }

            url = f"{self.wc_api_base}/products/categories"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                categories = await response.json()

            result = {
                "total": len(categories),
                "page": page,
                "categories": [
                    {
                        "id": cat["id"],
                        "name": cat["name"],
                        "slug": cat["slug"],
                        "description": cat.get("description", ""),
                        "count": cat.get("count", 0),
                        "parent": cat.get("parent", 0),
                    }
                    for cat in categories
                ],
            }

            return self._format_success_response(result, "list_product_categories")
        except Exception as e:
            return self._format_error_response(e, "list_product_categories")

    async def create_product_category(
        self, name: str, description: str | None = None, parent: int | None = None
    ) -> str:
        """Create a new WooCommerce product category."""
        try:
            data = {"name": name}
            if description:
                data["description"] = description
            if parent:
                data["parent"] = parent

            url = f"{self.wc_api_base}/products/categories"
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                category = await response.json()

            result = {
                "id": category["id"],
                "name": category["name"],
                "slug": category["slug"],
                "message": f"Product category '{name}' created successfully with ID {category['id']}",
            }

            return self._format_success_response(result, "create_product_category")
        except Exception as e:
            return self._format_error_response(e, "create_product_category")

    # === PRODUCT TAGS ===

    async def list_product_tags(
        self, per_page: int = 10, page: int = 1, hide_empty: bool = False
    ) -> str:
        """List WooCommerce product tags."""
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",
            }

            url = f"{self.wc_api_base}/products/tags"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                tags = await response.json()

            result = {
                "total": len(tags),
                "page": page,
                "tags": [
                    {
                        "id": tag["id"],
                        "name": tag["name"],
                        "slug": tag["slug"],
                        "description": tag.get("description", ""),
                        "count": tag.get("count", 0),
                    }
                    for tag in tags
                ],
            }

            return self._format_success_response(result, "list_product_tags")
        except Exception as e:
            return self._format_error_response(e, "list_product_tags")

    # === COUPONS ===

    async def list_coupons(
        self, per_page: int = 10, page: int = 1, search: str | None = None
    ) -> str:
        """List WooCommerce coupons."""
        try:
            params = {"per_page": per_page, "page": page}
            if search:
                params["search"] = search

            url = f"{self.wc_api_base}/coupons"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                coupons = await response.json()

            result = {
                "total": len(coupons),
                "page": page,
                "coupons": [
                    {
                        "id": coupon["id"],
                        "code": coupon["code"],
                        "discount_type": coupon["discount_type"],
                        "amount": coupon["amount"],
                        "description": coupon.get("description", ""),
                        "date_expires": coupon.get("date_expires"),
                        "usage_count": coupon.get("usage_count", 0),
                        "usage_limit": coupon.get("usage_limit"),
                        "individual_use": coupon.get("individual_use", False),
                        "free_shipping": coupon.get("free_shipping", False),
                        "minimum_amount": coupon.get("minimum_amount", "0"),
                        "maximum_amount": coupon.get("maximum_amount", "0"),
                    }
                    for coupon in coupons
                ],
            }

            return self._format_success_response(result, "list_coupons")
        except Exception as e:
            return self._format_error_response(e, "list_coupons")

    async def create_coupon(
        self,
        code: str,
        amount: str,
        discount_type: str = "percent",
        description: str | None = None,
        date_expires: str | None = None,
        minimum_amount: str | None = None,
        maximum_amount: str | None = None,
        individual_use: bool = False,
        product_ids: list[int] | None = None,
        excluded_product_ids: list[int] | None = None,
        usage_limit: int | None = None,
        usage_limit_per_user: int | None = None,
        limit_usage_to_x_items: int | None = None,
        free_shipping: bool = False,
    ) -> str:
        """Create a new WooCommerce coupon."""
        try:
            data = {
                "code": code,
                "discount_type": discount_type,
                "amount": amount,
                "individual_use": individual_use,
                "free_shipping": free_shipping,
            }

            # Add optional fields
            if description:
                data["description"] = description
            if date_expires:
                data["date_expires"] = date_expires
            if minimum_amount:
                data["minimum_amount"] = minimum_amount
            if maximum_amount:
                data["maximum_amount"] = maximum_amount
            if product_ids:
                data["product_ids"] = product_ids
            if excluded_product_ids:
                data["excluded_product_ids"] = excluded_product_ids
            if usage_limit:
                data["usage_limit"] = usage_limit
            if usage_limit_per_user:
                data["usage_limit_per_user"] = usage_limit_per_user
            if limit_usage_to_x_items:
                data["limit_usage_to_x_items"] = limit_usage_to_x_items

            url = f"{self.wc_api_base}/coupons"
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                coupon = await response.json()

            result = {
                "id": coupon["id"],
                "code": coupon["code"],
                "discount_type": coupon["discount_type"],
                "amount": coupon["amount"],
                "date_expires": coupon.get("date_expires"),
                "message": f"Coupon '{code}' created successfully with ID {coupon['id']}",
            }

            return self._format_success_response(result, "create_coupon")
        except Exception as e:
            return self._format_error_response(e, "create_coupon")

    async def update_coupon(self, coupon_id: int, **kwargs) -> str:
        """Update an existing WooCommerce coupon."""
        try:
            # Build update data from kwargs
            data = {k: v for k, v in kwargs.items() if v is not None}

            if not data:
                raise Exception("No update data provided")

            url = f"{self.wc_api_base}/coupons/{coupon_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.put(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                coupon = await response.json()

            result = {
                "id": coupon["id"],
                "code": coupon["code"],
                "discount_type": coupon["discount_type"],
                "amount": coupon["amount"],
                "message": f"Coupon ID {coupon_id} updated successfully",
            }

            return self._format_success_response(result, "update_coupon")
        except Exception as e:
            return self._format_error_response(e, "update_coupon")

    async def delete_coupon(self, coupon_id: int, force: bool = False) -> str:
        """Delete a WooCommerce coupon."""
        try:
            params = {"force": "true" if force else "false"}

            url = f"{self.wc_api_base}/coupons/{coupon_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.delete(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                await response.json()

            action = "permanently deleted" if force else "moved to trash"
            result = {"coupon_id": coupon_id, "message": f"Coupon {action} successfully"}

            return self._format_success_response(result, "delete_coupon")
        except Exception as e:
            return self._format_error_response(e, "delete_coupon")

    # === PRODUCT ATTRIBUTES & VARIATIONS ===

    async def list_product_attributes(self) -> str:
        """List all global product attributes."""
        try:
            url = f"{self.wc_api_base}/products/attributes"
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers={"Authorization": self.auth_header}) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                attributes = await response.json()

            result = {
                "total": len(attributes),
                "attributes": [
                    {
                        "id": attr["id"],
                        "name": attr["name"],
                        "slug": attr["slug"],
                        "type": attr.get("type", "select"),
                        "order_by": attr.get("order_by", "menu_order"),
                        "has_archives": attr.get("has_archives", False),
                    }
                    for attr in attributes
                ],
            }

            return self._format_success_response(result, "list_product_attributes")
        except Exception as e:
            return self._format_error_response(e, "list_product_attributes")

    async def create_product_attribute(
        self,
        name: str,
        slug: str | None = None,
        type: str = "select",
        order_by: str = "menu_order",
        has_archives: bool = False,
    ) -> str:
        """Create a new global product attribute."""
        try:
            data = {"name": name, "type": type, "order_by": order_by, "has_archives": has_archives}
            if slug:
                data["slug"] = slug

            url = f"{self.wc_api_base}/products/attributes"
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                attribute = await response.json()

            result = {
                "id": attribute["id"],
                "name": attribute["name"],
                "slug": attribute["slug"],
                "message": f"Product attribute '{name}' created successfully with ID {attribute['id']}",
            }

            return self._format_success_response(result, "create_product_attribute")
        except Exception as e:
            return self._format_error_response(e, "create_product_attribute")

    async def list_product_variations(
        self, product_id: int, per_page: int = 10, page: int = 1
    ) -> str:
        """List variations of a variable product."""
        try:
            params = {"per_page": per_page, "page": page}

            url = f"{self.wc_api_base}/products/{product_id}/variations"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                variations = await response.json()

            result = {
                "product_id": product_id,
                "total": len(variations),
                "page": page,
                "variations": [
                    {
                        "id": var["id"],
                        "sku": var.get("sku", ""),
                        "regular_price": var.get("regular_price", ""),
                        "sale_price": var.get("sale_price", ""),
                        "stock_status": var.get("stock_status", "instock"),
                        "stock_quantity": var.get("stock_quantity"),
                        "attributes": var.get("attributes", []),
                        "image": var.get("image"),
                        "permalink": var.get("permalink"),
                    }
                    for var in variations
                ],
            }

            return self._format_success_response(result, "list_product_variations")
        except Exception as e:
            return self._format_error_response(e, "list_product_variations")

    async def create_product_variation(
        self,
        product_id: int,
        attributes: list[dict[str, Any]],
        regular_price: str | None = None,
        sale_price: str | None = None,
        stock_quantity: int | None = None,
        stock_status: str = "instock",
        manage_stock: bool = False,
        sku: str | None = None,
        description: str | None = None,
        image: dict[str, int] | None = None,
    ) -> str:
        """Create a new variation for a variable product."""
        try:
            data = {
                "attributes": attributes,
                "stock_status": stock_status,
                "manage_stock": manage_stock,
            }

            # Add optional fields
            if regular_price:
                data["regular_price"] = regular_price
            if sale_price:
                data["sale_price"] = sale_price
            if stock_quantity is not None:
                data["stock_quantity"] = stock_quantity
            if sku:
                data["sku"] = sku
            if description:
                data["description"] = description
            if image:
                data["image"] = image

            url = f"{self.wc_api_base}/products/{product_id}/variations"
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                variation = await response.json()

            result = {
                "variation_id": variation["id"],
                "product_id": product_id,
                "attributes": variation["attributes"],
                "regular_price": variation.get("regular_price"),
                "sale_price": variation.get("sale_price"),
                "message": f"Product variation created successfully with ID {variation['id']}",
            }

            return self._format_success_response(result, "create_product_variation")
        except Exception as e:
            return self._format_error_response(e, "create_product_variation")

    # === REPORTS & ANALYTICS ===

    async def get_sales_report(
        self, period: str = "week", date_min: str | None = None, date_max: str | None = None
    ) -> str:
        """Get WooCommerce sales report."""
        try:
            params = {"period": period}
            if date_min:
                params["date_min"] = date_min
            if date_max:
                params["date_max"] = date_max

            url = f"{self.wc_api_base}/reports/sales"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    # Check if reports endpoint is not available
                    if response.status == 404:
                        raise Exception(
                            "Sales reports endpoint not available. "
                            "WooCommerce v3 API has limited reporting capabilities. "
                            "Consider using WooCommerce Analytics or custom queries."
                        )
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                report_data = await response.json()

            # Format the response based on what the API returns
            result = {
                "period": period,
                "sales_data": report_data if isinstance(report_data, list) else [report_data],
                "note": "WooCommerce v3 API has limited reporting. For advanced analytics, use WooCommerce Analytics extension.",
            }

            return self._format_success_response(result, "get_sales_report")
        except Exception as e:
            return self._format_error_response(e, "get_sales_report")

    async def get_top_sellers(
        self, period: str = "week", date_min: str | None = None, date_max: str | None = None
    ) -> str:
        """Get top selling products report."""
        try:
            params = {"period": period}
            if date_min:
                params["date_min"] = date_min
            if date_max:
                params["date_max"] = date_max

            url = f"{self.wc_api_base}/reports/top_sellers"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    if response.status == 404:
                        raise Exception(
                            "Top sellers endpoint not available. "
                            "WooCommerce v3 API has limited reporting capabilities."
                        )
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                top_sellers = await response.json()

            result = {
                "period": period,
                "total_products": len(top_sellers) if isinstance(top_sellers, list) else 0,
                "top_sellers": [
                    {
                        "product_id": item.get("product_id"),
                        "title": item.get("title"),
                        "quantity": item.get("quantity", 0),
                    }
                    for item in (top_sellers if isinstance(top_sellers, list) else [])
                ],
            }

            return self._format_success_response(result, "get_top_sellers")
        except Exception as e:
            return self._format_error_response(e, "get_top_sellers")

    async def get_customer_report(
        self, period: str = "week", date_min: str | None = None, date_max: str | None = None
    ) -> str:
        """Get customer statistics report."""
        try:
            params = {"period": period}
            if date_min:
                params["date_min"] = date_min
            if date_max:
                params["date_max"] = date_max

            url = f"{self.wc_api_base}/reports/customers"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    if response.status == 404:
                        # Fallback: Use customers list endpoint if reports not available
                        return await self._get_customer_report_fallback()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                customer_data = await response.json()

            result = {
                "period": period,
                "customer_data": (
                    customer_data if isinstance(customer_data, list) else [customer_data]
                ),
                "note": "Customer reporting may be limited in WooCommerce v3 API.",
            }

            return self._format_success_response(result, "get_customer_report")
        except Exception as e:
            return self._format_error_response(e, "get_customer_report")

    async def _get_customer_report_fallback(self) -> str:
        """Fallback method when customer reports endpoint is not available."""
        try:
            # Use customers list to generate basic stats
            url = f"{self.wc_api_base}/customers"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params={"per_page": 100}, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    raise Exception("Customer report and fallback both unavailable")

                customers = await response.json()

            # Calculate basic stats
            total_customers = len(customers)
            total_spent = sum(float(c.get("total_spent", 0)) for c in customers)
            avg_spent = total_spent / total_customers if total_customers > 0 else 0

            result = {
                "total_customers": total_customers,
                "total_spent": f"{total_spent:.2f}",
                "average_spent_per_customer": f"{avg_spent:.2f}",
                "note": "Generated from customer list (fallback method). For detailed analytics, use WooCommerce Analytics.",
            }

            return self._format_success_response(result, "get_customer_report")
        except Exception as e:
            return self._format_error_response(e, "get_customer_report")

    # === ORDERS ===

    async def list_orders(
        self,
        per_page: int = 10,
        page: int = 1,
        status: str | None = None,
        customer: int | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> str:
        """
        List WooCommerce orders with filters.

        Args:
            per_page: Number of orders per page (default: 10)
            page: Page number (default: 1)
            status: Filter by order status (any, pending, processing, on-hold, completed, cancelled, refunded, failed, trash)
            customer: Filter by customer ID
            after: Filter orders after this date (ISO 8601 format)
            before: Filter orders before this date (ISO 8601 format)
        """
        try:
            # Build query parameters
            params = {"per_page": per_page, "page": page}

            # Add optional filters
            if status:
                params["status"] = status
            if customer is not None:
                params["customer"] = customer
            if after:
                params["after"] = after
            if before:
                params["before"] = before

            # Make request to WooCommerce API
            url = f"{self.wc_api_base}/orders"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                orders = await response.json()

            # Format response
            result = {
                "total": len(orders),
                "page": page,
                "per_page": per_page,
                "orders": [
                    {
                        "id": order["id"],
                        "number": order["number"],
                        "status": order["status"],
                        "date_created": order["date_created"],
                        "date_modified": order.get("date_modified", ""),
                        "total": order["total"],
                        "currency": order["currency"],
                        "customer_id": order["customer_id"],
                        "billing": {
                            "first_name": order["billing"].get("first_name", ""),
                            "last_name": order["billing"].get("last_name", ""),
                            "email": order["billing"].get("email", ""),
                        },
                        "line_items_count": len(order.get("line_items", [])),
                        "payment_method_title": order.get("payment_method_title", ""),
                        "transaction_id": order.get("transaction_id", ""),
                    }
                    for order in orders
                ],
            }

            return self._format_success_response(result, "list_orders")
        except Exception as e:
            return self._format_error_response(e, "list_orders")

    async def get_order(self, order_id: int) -> str:
        """
        Get detailed information about a specific order.

        Args:
            order_id: Order ID
        """
        try:
            url = f"{self.wc_api_base}/orders/{order_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers={"Authorization": self.auth_header}) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                order = await response.json()

            # Format detailed response
            result = {
                "id": order["id"],
                "number": order["number"],
                "status": order["status"],
                "currency": order["currency"],
                "date_created": order["date_created"],
                "date_modified": order.get("date_modified", ""),
                "discount_total": order["discount_total"],
                "shipping_total": order["shipping_total"],
                "total": order["total"],
                "total_tax": order["total_tax"],
                "customer_id": order["customer_id"],
                "customer_note": order.get("customer_note", ""),
                "billing": order["billing"],
                "shipping": order["shipping"],
                "payment_method": order["payment_method"],
                "payment_method_title": order.get("payment_method_title", ""),
                "transaction_id": order.get("transaction_id", ""),
                "line_items": [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "product_id": item["product_id"],
                        "quantity": item["quantity"],
                        "subtotal": item["subtotal"],
                        "total": item["total"],
                        "sku": item.get("sku", ""),
                    }
                    for item in order.get("line_items", [])
                ],
                "shipping_lines": order.get("shipping_lines", []),
                "fee_lines": order.get("fee_lines", []),
                "coupon_lines": order.get("coupon_lines", []),
            }

            return self._format_success_response(result, "get_order")
        except Exception as e:
            return self._format_error_response(e, "get_order")

    async def update_order_status(self, order_id: int, status: str) -> str:
        """
        Update order status.

        Args:
            order_id: Order ID
            status: New status (pending, processing, on-hold, completed, cancelled, refunded, failed)
        """
        try:
            data = {"status": status}

            url = f"{self.wc_api_base}/orders/{order_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.put(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                order = await response.json()

            result = {
                "id": order["id"],
                "number": order["number"],
                "status": order["status"],
                "message": f"Order #{order['number']} status updated to '{status}'",
            }

            return self._format_success_response(result, "update_order_status")
        except Exception as e:
            return self._format_error_response(e, "update_order_status")

    async def create_order(
        self,
        customer_id: int | None = None,
        line_items: list[dict] | None = None,
        billing: dict | None = None,
        shipping: dict | None = None,
        payment_method: str | None = None,
        status: str = "pending",
    ) -> str:
        """
        Create a new order.

        Args:
            customer_id: Customer ID (optional)
            line_items: List of line items [{"product_id": 123, "quantity": 1}]
            billing: Billing address dictionary
            shipping: Shipping address dictionary
            payment_method: Payment method ID
            status: Order status (default: pending)
        """
        try:
            data = {"status": status}

            if customer_id is not None:
                data["customer_id"] = customer_id
            if line_items:
                data["line_items"] = line_items
            if billing:
                data["billing"] = billing
            if shipping:
                data["shipping"] = shipping
            if payment_method:
                data["payment_method"] = payment_method

            url = f"{self.wc_api_base}/orders"
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                order = await response.json()

            result = {
                "id": order["id"],
                "number": order["number"],
                "status": order["status"],
                "total": order["total"],
                "currency": order["currency"],
                "message": f"Order #{order['number']} created successfully with ID {order['id']}",
            }

            return self._format_success_response(result, "create_order")
        except Exception as e:
            return self._format_error_response(e, "create_order")

    async def delete_order(self, order_id: int, force: bool = False) -> str:
        """
        Delete an order.

        Args:
            order_id: Order ID
            force: Force delete (true) or move to trash (false)
        """
        try:
            params = {"force": "true" if force else "false"}

            url = f"{self.wc_api_base}/orders/{order_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.delete(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                await response.json()

            message = f"Order {order_id} {'permanently deleted' if force else 'moved to trash'}"
            return self._format_success_response({"message": message}, "delete_order")
        except Exception as e:
            return self._format_error_response(e, "delete_order")

    # === CUSTOMERS ===

    async def list_customers(
        self,
        per_page: int = 10,
        page: int = 1,
        search: str | None = None,
        email: str | None = None,
        role: str | None = None,
    ) -> str:
        """
        List WooCommerce customers.

        Args:
            per_page: Number of customers per page (default: 10)
            page: Page number (default: 1)
            search: Search by name or email
            email: Filter by specific email
            role: Filter by role (customer, subscriber, etc.)
        """
        try:
            # Build query parameters
            params = {"per_page": per_page, "page": page}

            # Add optional filters
            if search:
                params["search"] = search
            if email:
                params["email"] = email
            if role:
                params["role"] = role

            # Make request to WooCommerce API
            url = f"{self.wc_api_base}/customers"
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                customers = await response.json()

            # Format response
            result = {
                "total": len(customers),
                "page": page,
                "per_page": per_page,
                "customers": [
                    {
                        "id": customer["id"],
                        "email": customer["email"],
                        "first_name": customer.get("first_name", ""),
                        "last_name": customer.get("last_name", ""),
                        "username": customer.get("username", ""),
                        "role": customer.get("role", ""),
                        "date_created": customer.get("date_created", ""),
                        "orders_count": customer.get("orders_count", 0),
                        "total_spent": customer.get("total_spent", "0"),
                        "avatar_url": customer.get("avatar_url", ""),
                    }
                    for customer in customers
                ],
            }

            return self._format_success_response(result, "list_customers")
        except Exception as e:
            return self._format_error_response(e, "list_customers")

    async def get_customer(self, customer_id: int) -> str:
        """
        Get detailed information about a specific customer.

        Args:
            customer_id: Customer ID
        """
        try:
            url = f"{self.wc_api_base}/customers/{customer_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers={"Authorization": self.auth_header}) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                customer = await response.json()

            # Format detailed response
            result = {
                "id": customer["id"],
                "email": customer["email"],
                "username": customer.get("username", ""),
                "first_name": customer.get("first_name", ""),
                "last_name": customer.get("last_name", ""),
                "role": customer.get("role", ""),
                "date_created": customer.get("date_created", ""),
                "date_modified": customer.get("date_modified", ""),
                "orders_count": customer.get("orders_count", 0),
                "total_spent": customer.get("total_spent", "0"),
                "avatar_url": customer.get("avatar_url", ""),
                "billing": customer.get("billing", {}),
                "shipping": customer.get("shipping", {}),
                "is_paying_customer": customer.get("is_paying_customer", False),
            }

            return self._format_success_response(result, "get_customer")
        except Exception as e:
            return self._format_error_response(e, "get_customer")

    async def create_customer(
        self,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
        username: str | None = None,
        password: str | None = None,
        billing: dict | None = None,
        shipping: dict | None = None,
    ) -> str:
        """
        Create a new customer.

        Args:
            email: Customer email (required)
            first_name: First name
            last_name: Last name
            username: Username (will be generated from email if not provided)
            password: Password (will be auto-generated if not provided)
            billing: Billing address dictionary
            shipping: Shipping address dictionary
        """
        try:
            data = {"email": email}

            if first_name:
                data["first_name"] = first_name
            if last_name:
                data["last_name"] = last_name
            if username:
                data["username"] = username
            if password:
                data["password"] = password
            if billing:
                data["billing"] = billing
            if shipping:
                data["shipping"] = shipping

            url = f"{self.wc_api_base}/customers"
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                customer = await response.json()

            result = {
                "id": customer["id"],
                "email": customer["email"],
                "username": customer.get("username", ""),
                "first_name": customer.get("first_name", ""),
                "last_name": customer.get("last_name", ""),
                "message": f"Customer created successfully with ID {customer['id']}",
            }

            return self._format_success_response(result, "create_customer")
        except Exception as e:
            return self._format_error_response(e, "create_customer")

    async def update_customer(self, customer_id: int, **kwargs) -> str:
        """
        Update an existing customer.

        Args:
            customer_id: Customer ID
            **kwargs: Fields to update (first_name, last_name, email, billing, shipping, etc.)
        """
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}

            url = f"{self.wc_api_base}/customers/{customer_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.put(
                    url, json=data, headers={"Authorization": self.auth_header}
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WooCommerce API error ({response.status}): {error_text}")

                customer = await response.json()

            result = {
                "id": customer["id"],
                "email": customer["email"],
                "first_name": customer.get("first_name", ""),
                "last_name": customer.get("last_name", ""),
                "message": f"Customer {customer_id} updated successfully",
            }

            return self._format_success_response(result, "update_customer")
        except Exception as e:
            return self._format_error_response(e, "update_customer")

    # ========================================
    # SEO Methods (Rank Math / Yoast)
    # ========================================

    async def get_post_seo(self, post_id: int) -> str:
        """
        Get SEO metadata for a post or page.

        Args:
            post_id: Post or Page ID
        """
        try:
            result = await self._make_request("GET", f"posts/{post_id}")

            # Extract SEO meta fields
            meta = result.get("meta", {})

            # Check which SEO plugin is active
            has_rank_math = "rank_math_focus_keyword" in meta
            has_yoast = "_yoast_wpseo_focuskw" in meta

            if not has_rank_math and not has_yoast:
                return self._format_error_response(
                    Exception(
                        "SEO API Bridge plugin not detected. Please install and activate the SEO API Bridge WordPress plugin."
                    ),
                    "get_post_seo",
                )

            # Format SEO data
            seo_data = {
                "post_id": post_id,
                "post_title": result.get("title", {}).get("rendered", ""),
                "plugin_detected": "rank_math" if has_rank_math else "yoast",
            }

            if has_rank_math:
                seo_data.update(
                    {
                        "focus_keyword": meta.get("rank_math_focus_keyword", ""),
                        "seo_title": meta.get("rank_math_seo_title", ""),
                        "meta_description": meta.get("rank_math_description", ""),
                        "additional_keywords": meta.get("rank_math_additional_keywords", ""),
                        "canonical_url": meta.get("rank_math_canonical_url", ""),
                        "robots": meta.get("rank_math_robots", []),
                        "breadcrumb_title": meta.get("rank_math_breadcrumb_title", ""),
                        "open_graph": {
                            "title": meta.get("rank_math_facebook_title", ""),
                            "description": meta.get("rank_math_facebook_description", ""),
                            "image": meta.get("rank_math_facebook_image", ""),
                            "image_id": meta.get("rank_math_facebook_image_id", ""),
                        },
                        "twitter": {
                            "title": meta.get("rank_math_twitter_title", ""),
                            "description": meta.get("rank_math_twitter_description", ""),
                            "image": meta.get("rank_math_twitter_image", ""),
                            "image_id": meta.get("rank_math_twitter_image_id", ""),
                            "card_type": meta.get("rank_math_twitter_card_type", ""),
                        },
                    }
                )
            elif has_yoast:
                seo_data.update(
                    {
                        "focus_keyword": meta.get("_yoast_wpseo_focuskw", ""),
                        "seo_title": meta.get("_yoast_wpseo_title", ""),
                        "meta_description": meta.get("_yoast_wpseo_metadesc", ""),
                        "canonical_url": meta.get("_yoast_wpseo_canonical", ""),
                        "noindex": meta.get("_yoast_wpseo_meta-robots-noindex", ""),
                        "nofollow": meta.get("_yoast_wpseo_meta-robots-nofollow", ""),
                        "breadcrumb_title": meta.get("_yoast_wpseo_bctitle", ""),
                        "open_graph": {
                            "title": meta.get("_yoast_wpseo_opengraph-title", ""),
                            "description": meta.get("_yoast_wpseo_opengraph-description", ""),
                            "image": meta.get("_yoast_wpseo_opengraph-image", ""),
                            "image_id": meta.get("_yoast_wpseo_opengraph-image-id", ""),
                        },
                        "twitter": {
                            "title": meta.get("_yoast_wpseo_twitter-title", ""),
                            "description": meta.get("_yoast_wpseo_twitter-description", ""),
                            "image": meta.get("_yoast_wpseo_twitter-image", ""),
                            "image_id": meta.get("_yoast_wpseo_twitter-image-id", ""),
                        },
                    }
                )

            return self._format_success_response(seo_data, "get_post_seo")
        except Exception as e:
            return self._format_error_response(e, "get_post_seo")

    async def update_post_seo(
        self,
        post_id: int,
        focus_keyword: str | None = None,
        seo_title: str | None = None,
        meta_description: str | None = None,
        additional_keywords: str | None = None,
        canonical_url: str | None = None,
        robots: list[str] | None = None,
        og_title: str | None = None,
        og_description: str | None = None,
        og_image: str | None = None,
        twitter_title: str | None = None,
        twitter_description: str | None = None,
        twitter_image: str | None = None,
    ) -> str:
        """
        Update SEO metadata for a post or page.

        Automatically detects whether Rank Math or Yoast is active and uses appropriate field names.

        Args:
            post_id: Post or Page ID
            focus_keyword: Primary focus keyword
            seo_title: Meta title
            meta_description: Meta description
            additional_keywords: Additional keywords
            canonical_url: Canonical URL
            robots: Robots meta directives
            og_title: Open Graph title
            og_description: Open Graph description
            og_image: Open Graph image URL
            twitter_title: Twitter Card title
            twitter_description: Twitter Card description
            twitter_image: Twitter Card image URL
        """
        try:
            # First check which SEO plugin is active
            seo_check = await self.check_seo_plugins()

            if not seo_check.get("api_bridge_active"):
                return self._format_error_response(
                    Exception(
                        "SEO API Bridge plugin not detected. Please install and activate the SEO API Bridge WordPress plugin."
                    ),
                    "update_post_seo",
                )

            # Build meta object based on active plugin
            meta = {}

            if seo_check.get("rank_math", {}).get("active"):
                # Use Rank Math field names
                if focus_keyword is not None:
                    meta["rank_math_focus_keyword"] = focus_keyword
                if seo_title is not None:
                    meta["rank_math_seo_title"] = seo_title
                if meta_description is not None:
                    meta["rank_math_description"] = meta_description
                if additional_keywords is not None:
                    meta["rank_math_additional_keywords"] = additional_keywords
                if canonical_url is not None:
                    meta["rank_math_canonical_url"] = canonical_url
                if robots is not None:
                    meta["rank_math_robots"] = robots
                if og_title is not None:
                    meta["rank_math_facebook_title"] = og_title
                if og_description is not None:
                    meta["rank_math_facebook_description"] = og_description
                if og_image is not None:
                    meta["rank_math_facebook_image"] = og_image
                if twitter_title is not None:
                    meta["rank_math_twitter_title"] = twitter_title
                if twitter_description is not None:
                    meta["rank_math_twitter_description"] = twitter_description
                if twitter_image is not None:
                    meta["rank_math_twitter_image"] = twitter_image

            elif seo_check.get("yoast", {}).get("active"):
                # Use Yoast field names
                if focus_keyword is not None:
                    meta["_yoast_wpseo_focuskw"] = focus_keyword
                if seo_title is not None:
                    meta["_yoast_wpseo_title"] = seo_title
                if meta_description is not None:
                    meta["_yoast_wpseo_metadesc"] = meta_description
                if canonical_url is not None:
                    meta["_yoast_wpseo_canonical"] = canonical_url
                if og_title is not None:
                    meta["_yoast_wpseo_opengraph-title"] = og_title
                if og_description is not None:
                    meta["_yoast_wpseo_opengraph-description"] = og_description
                if og_image is not None:
                    meta["_yoast_wpseo_opengraph-image"] = og_image
                if twitter_title is not None:
                    meta["_yoast_wpseo_twitter-title"] = twitter_title
                if twitter_description is not None:
                    meta["_yoast_wpseo_twitter-description"] = twitter_description
                if twitter_image is not None:
                    meta["_yoast_wpseo_twitter-image"] = twitter_image

            # Update post with meta fields
            data = {"meta": meta}
            await self._make_request("POST", f"posts/{post_id}", json_data=data)

            response = {
                "post_id": post_id,
                "updated_fields": list(meta.keys()),
                "message": f"SEO metadata updated successfully for post {post_id}",
            }

            return self._format_success_response(response, "update_post_seo")
        except Exception as e:
            return self._format_error_response(e, "update_post_seo")

    async def update_product_seo(
        self,
        product_id: int,
        focus_keyword: str | None = None,
        seo_title: str | None = None,
        meta_description: str | None = None,
        additional_keywords: str | None = None,
        canonical_url: str | None = None,
        og_title: str | None = None,
        og_description: str | None = None,
        og_image: str | None = None,
    ) -> str:
        """
        Update SEO metadata for a WooCommerce product.

        Same as update_post_seo but uses the product endpoint.

        Args:
            product_id: Product ID
            focus_keyword: Primary focus keyword
            seo_title: Meta title
            meta_description: Meta description
            additional_keywords: Additional keywords
            canonical_url: Canonical URL
            og_title: Open Graph title
            og_description: Open Graph description
            og_image: Open Graph image URL
        """
        try:
            # First check which SEO plugin is active
            seo_check = await self.check_seo_plugins()

            if not seo_check.get("api_bridge_active"):
                return self._format_error_response(
                    Exception(
                        "SEO API Bridge plugin not detected. Please install and activate the SEO API Bridge WordPress plugin."
                    ),
                    "update_product_seo",
                )

            # Build meta object based on active plugin
            meta = {}

            if seo_check.get("rank_math", {}).get("active"):
                # Use Rank Math field names
                if focus_keyword is not None:
                    meta["rank_math_focus_keyword"] = focus_keyword
                if seo_title is not None:
                    meta["rank_math_seo_title"] = seo_title
                if meta_description is not None:
                    meta["rank_math_description"] = meta_description
                if additional_keywords is not None:
                    meta["rank_math_additional_keywords"] = additional_keywords
                if canonical_url is not None:
                    meta["rank_math_canonical_url"] = canonical_url
                if og_title is not None:
                    meta["rank_math_facebook_title"] = og_title
                if og_description is not None:
                    meta["rank_math_facebook_description"] = og_description
                if og_image is not None:
                    meta["rank_math_facebook_image"] = og_image

            elif seo_check.get("yoast", {}).get("active"):
                # Use Yoast field names
                if focus_keyword is not None:
                    meta["_yoast_wpseo_focuskw"] = focus_keyword
                if seo_title is not None:
                    meta["_yoast_wpseo_title"] = seo_title
                if meta_description is not None:
                    meta["_yoast_wpseo_metadesc"] = meta_description
                if canonical_url is not None:
                    meta["_yoast_wpseo_canonical"] = canonical_url
                if og_title is not None:
                    meta["_yoast_wpseo_opengraph-title"] = og_title
                if og_description is not None:
                    meta["_yoast_wpseo_opengraph-description"] = og_description
                if og_image is not None:
                    meta["_yoast_wpseo_opengraph-image"] = og_image

            # Update product via WordPress REST API (WooCommerce products are post type 'product')
            data = {"meta": meta}

            # Use regular WordPress API with product endpoint (singular - custom post type)
            url = f"{self.api_base}/product/{product_id}"
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url,
                    json=data,
                    headers={"Authorization": self.auth_header, "Content-Type": "application/json"},
                ) as response,
            ):
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"WordPress API error ({response.status}): {error_text}")

                await response.json()

            response = {
                "product_id": product_id,
                "updated_fields": list(meta.keys()),
                "message": f"SEO metadata updated successfully for product {product_id}",
            }

            return self._format_success_response(response, "update_product_seo")
        except Exception as e:
            return self._format_error_response(e, "update_product_seo")

    # =========================================================================
    # Phase 5: WP-CLI Integration
    # =========================================================================

    async def wp_cache_flush(self) -> str:
        """
        Flush WordPress object cache via WP-CLI.

        Clears all cached objects from the object cache (Redis, Memcached, or file).
        Safe to run anytime - will not affect database or content.

        Returns:
            JSON string with status and message

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_cache_flush",
                )

            result = await self.wp_cli.wp_cache_flush()
            return self._format_success_response(result, "wp_cache_flush")
        except Exception as e:
            return self._format_error_response(e, "wp_cache_flush")

    async def wp_cache_type(self) -> str:
        """
        Get the object cache type being used via WP-CLI.

        Shows which caching backend is active (e.g., Redis, Memcached, file-based).

        Returns:
            JSON string with cache type information

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_cache_type",
                )

            result = await self.wp_cli.wp_cache_type()
            return self._format_success_response(result, "wp_cache_type")
        except Exception as e:
            return self._format_error_response(e, "wp_cache_type")

    async def wp_transient_delete_all(self) -> str:
        """
        Delete all expired transients from the database via WP-CLI.

        Transients are temporary cached data stored in the WordPress database.
        This command only deletes expired transients, improving database performance.

        Returns:
            JSON string with count of deleted transients

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_transient_delete_all",
                )

            result = await self.wp_cli.wp_transient_delete_all()
            return self._format_success_response(result, "wp_transient_delete_all")
        except Exception as e:
            return self._format_error_response(e, "wp_transient_delete_all")

    async def wp_transient_list(self) -> str:
        """
        List all transients in the database via WP-CLI.

        Shows all transient keys with their expiration times.
        Useful for debugging caching issues.

        Returns:
            JSON string with total count and list of transients

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_transient_list",
                )

            result = await self.wp_cli.wp_transient_list()
            return self._format_success_response(result, "wp_transient_list")
        except Exception as e:
            return self._format_error_response(e, "wp_transient_list")

    # =========================================================================
    # Phase 5.2: Database Operations (3 tools)
    # =========================================================================

    async def wp_db_check(self) -> str:
        """
        Check WordPress database health via WP-CLI.

        Runs database integrity checks to ensure tables are healthy.
        Safe operation - read-only.

        Returns:
            JSON string with health status and tables checked

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_db_check",
                )

            result = await self.wp_cli.wp_db_check()
            return self._format_success_response(result, "wp_db_check")
        except Exception as e:
            return self._format_error_response(e, "wp_db_check")

    async def wp_db_optimize(self) -> str:
        """
        Optimize WordPress database tables via WP-CLI.

        Runs OPTIMIZE TABLE on all WordPress tables to reclaim space
        and improve performance. Safe operation - non-destructive.

        Returns:
            JSON string with optimization results

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_db_optimize",
                )

            result = await self.wp_cli.wp_db_optimize()
            return self._format_success_response(result, "wp_db_optimize")
        except Exception as e:
            return self._format_error_response(e, "wp_db_optimize")

    async def wp_db_export(self) -> str:
        """
        Export WordPress database to SQL file via WP-CLI.

        Creates a database backup in the /tmp directory with timestamp.
        Safe - exports are only saved to /tmp for security.

        Returns:
            JSON string with export file path and size

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_db_export",
                )

            result = await self.wp_cli.wp_db_export()
            return self._format_success_response(result, "wp_db_export")
        except Exception as e:
            return self._format_error_response(e, "wp_db_export")

    # =========================================================================
    # Phase 5.2: Plugin/Theme Info (4 tools)
    # =========================================================================

    async def wp_plugin_list_detailed(self) -> str:
        """
        List all WordPress plugins with detailed information via WP-CLI.

        Shows plugin names, versions, status (active/inactive), and available updates.
        Useful for inventory management and update planning.

        Returns:
            JSON string with total count and plugin list

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_plugin_list_detailed",
                )

            result = await self.wp_cli.wp_plugin_list_detailed()
            return self._format_success_response(result, "wp_plugin_list_detailed")
        except Exception as e:
            return self._format_error_response(e, "wp_plugin_list_detailed")

    async def wp_theme_list_detailed(self) -> str:
        """
        List all WordPress themes with detailed information via WP-CLI.

        Shows theme names, versions, status, and identifies the active theme.
        Useful for theme management and updates.

        Returns:
            JSON string with total count, theme list, and active theme

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_theme_list_detailed",
                )

            result = await self.wp_cli.wp_theme_list_detailed()
            return self._format_success_response(result, "wp_theme_list_detailed")
        except Exception as e:
            return self._format_error_response(e, "wp_theme_list_detailed")

    async def wp_plugin_verify_checksums(self) -> str:
        """
        Verify plugin file integrity via WP-CLI.

        Checks all plugins against WordPress.org checksums to detect tampering or corruption.
        Important security tool for detecting malware or unauthorized modifications.

        Note: Only works for plugins from WordPress.org repository.
        Premium/custom plugins will be skipped.

        Returns:
            JSON string with verification results

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_plugin_verify_checksums",
                )

            result = await self.wp_cli.wp_plugin_verify_checksums()
            return self._format_success_response(result, "wp_plugin_verify_checksums")
        except Exception as e:
            return self._format_error_response(e, "wp_plugin_verify_checksums")

    async def wp_core_verify_checksums(self) -> str:
        """
        Verify WordPress core files via WP-CLI.

        Checks WordPress core files for tampering, corruption, or unauthorized modifications.
        Critical security tool for ensuring WordPress integrity.

        Returns:
            JSON string with verification status and any modified files

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_core_verify_checksums",
                )

            result = await self.wp_cli.wp_core_verify_checksums()
            return self._format_success_response(result, "wp_core_verify_checksums")
        except Exception as e:
            return self._format_error_response(e, "wp_core_verify_checksums")

    # =========================================================================
    # Phase 5.3: Search & Replace + Update Tools
    # =========================================================================

    async def wp_search_replace_dry_run(
        self, old_string: str, new_string: str, tables: list[str] | None = None
    ) -> str:
        """
        Search and replace in database (DRY RUN ONLY) via WP-CLI.

        Previews what would be changed if you run search-replace.
        ALWAYS runs in dry-run mode - never makes actual changes.

        Security: This tool ONLY shows what would be changed. To make actual
        changes, you must use WP-CLI directly with appropriate backups.

        Args:
            old_string: String to search for
            new_string: String to replace with
            tables: Optional list of specific tables to search

        Returns:
            JSON string with preview of changes

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_search_replace_dry_run",
                )

            result = await self.wp_cli.wp_search_replace_dry_run(
                old_string=old_string, new_string=new_string, tables=tables
            )
            return self._format_success_response(result, "wp_search_replace_dry_run")
        except Exception as e:
            return self._format_error_response(e, "wp_search_replace_dry_run")

    async def wp_plugin_update(self, plugin_name: str, dry_run: bool = True) -> str:
        """
        Update WordPress plugin(s) via WP-CLI - DRY RUN by default.

        Shows available updates or performs actual update.
        Default behavior is DRY RUN for safety.

        Security:
        - Default: dry_run=True (only shows what would be updated)
        - Before actual update: backup database and files
        - Check plugin compatibility before major version updates

        Args:
            plugin_name: Plugin slug or "all" for all plugins
            dry_run: If True, only show available updates (default: True)

        Returns:
            JSON string with update information or results

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_plugin_update",
                )

            result = await self.wp_cli.wp_plugin_update(plugin_name=plugin_name, dry_run=dry_run)
            return self._format_success_response(result, "wp_plugin_update")
        except Exception as e:
            return self._format_error_response(e, "wp_plugin_update")

    async def wp_theme_update(self, theme_name: str, dry_run: bool = True) -> str:
        """
        Update WordPress theme(s) via WP-CLI - DRY RUN by default.

        Shows available updates or performs actual update.
        Default behavior is DRY RUN for safety.

        Security:
        - Default: dry_run=True (only shows what would be updated)
        - Before actual update: backup database and files
        - Test theme compatibility after updates
        - WARNING: Updating active theme can break site appearance

        Args:
            theme_name: Theme slug or "all" for all themes
            dry_run: If True, only show available updates (default: True)

        Returns:
            JSON string with update information or results

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_theme_update",
                )

            result = await self.wp_cli.wp_theme_update(theme_name=theme_name, dry_run=dry_run)
            return self._format_success_response(result, "wp_theme_update")
        except Exception as e:
            return self._format_error_response(e, "wp_theme_update")

    async def wp_core_update(self, version: str | None = None, dry_run: bool = True) -> str:
        """
        Update WordPress core via WP-CLI - DRY RUN by default.

        Shows available updates or performs actual core update.
        Default behavior is DRY RUN for safety.

        Security:
        - Default: dry_run=True (only shows what would be updated)
        - CRITICAL: Always backup database and files before core updates
        - Check plugin/theme compatibility before major version updates
        - Test thoroughly on staging environment first
        - Major version updates may have breaking changes

        Args:
            version: Specific version to update to, or None for latest
            dry_run: If True, only show available updates (default: True)

        Returns:
            JSON string with update information or results

        Requires:
            - Container name configured in environment variables
            - WP-CLI installed in WordPress container
            - Docker socket access
        """
        try:
            if not self.wp_cli:
                return self._format_error_response(
                    Exception(
                        "WP-CLI tools require 'container' configuration. "
                        f"Please set WORDPRESS_{self.project_id.upper()}_CONTAINER in your environment variables."
                    ),
                    "wp_core_update",
                )

            result = await self.wp_cli.wp_core_update(version=version, dry_run=dry_run)
            return self._format_success_response(result, "wp_core_update")
        except Exception as e:
            return self._format_error_response(e, "wp_core_update")

    # =========================================================================
    # Phase 6.1: Navigation Menus (6 tools)
    # =========================================================================

    async def list_menus(self) -> str:
        """
        List all WordPress navigation menus.

        Returns list of all menus with their locations and item counts.

        Returns:
            JSON string with total count and menu list

        Example response:
            {
              "total": 3,
              "menus": [
                {
                  "id": 2,
                  "name": "Primary Menu",
                  "slug": "primary-menu",
                  "locations": ["primary"],
                  "count": 8
                }
              ]
            }
        """
        try:
            # WordPress REST API for menus (requires plugin support)
            # Try custom endpoint first, fallback to standard if not available
            try:
                menus = await self._make_request("GET", "menus", use_custom_namespace=True)
            except:
                # Fallback: use wp/v2/navigation endpoint (WP 5.9+)
                menus = await self._make_request("GET", "navigation")

            result = {"total": len(menus) if isinstance(menus, list) else 0, "menus": menus}
            return self._format_success_response(result, "list_menus")
        except Exception as e:
            return self._format_error_response(e, "list_menus")

    async def get_menu(self, menu_id: int) -> str:
        """
        Get detailed information about a specific menu including all items.

        Args:
            menu_id: Menu ID

        Returns:
            JSON string with menu details and items
        """
        try:
            # Get menu details
            try:
                menu = await self._make_request(
                    "GET", f"menus/{menu_id}", use_custom_namespace=True
                )
            except:
                menu = await self._make_request("GET", f"navigation/{menu_id}")

            # Get menu items
            menu_items = await self.list_menu_items(menu_id)

            result = {
                "menu": menu,
                "items": json.loads(menu_items) if isinstance(menu_items, str) else menu_items,
            }
            return self._format_success_response(result, "get_menu")
        except Exception as e:
            return self._format_error_response(e, "get_menu")

    async def create_menu(
        self, name: str, slug: str | None = None, locations: list[str] | None = None
    ) -> str:
        """
        Create a new navigation menu.

        Args:
            name: Menu name
            slug: Menu slug (auto-generated if not provided)
            locations: Theme locations to assign menu to

        Returns:
            JSON string with created menu details
        """
        try:
            data = {"name": name}
            if slug:
                data["slug"] = slug
            if locations:
                data["locations"] = locations

            try:
                menu = await self._make_request(
                    "POST", "menus", json_data=data, use_custom_namespace=True
                )
            except:
                # Try navigation endpoint
                menu = await self._make_request("POST", "navigation", json_data=data)

            return self._format_success_response(menu, "create_menu")
        except Exception as e:
            return self._format_error_response(e, "create_menu")

    async def list_menu_items(self, menu_id: int) -> str:
        """
        List all items in a specific menu.

        Args:
            menu_id: Menu ID

        Returns:
            JSON string with menu items list
        """
        try:
            params = {"menus": menu_id, "per_page": 100}
            items = await self._make_request("GET", "menu-items", params=params)

            result = {
                "total": len(items) if isinstance(items, list) else 0,
                "menu_id": menu_id,
                "items": items,
            }
            return self._format_success_response(result, "list_menu_items")
        except Exception as e:
            return self._format_error_response(e, "list_menu_items")

    async def create_menu_item(
        self,
        menu_id: int,
        title: str,
        type: str,
        object_id: int | None = None,
        url: str | None = None,
        parent: int | None = None,
    ) -> str:
        """
        Add a new item to a menu.

        Args:
            menu_id: Menu ID to add item to
            title: Item title/label
            type: Item type (post_type, taxonomy, custom)
            object_id: ID of linked post/term (required for post_type/taxonomy)
            url: Custom URL (required for type=custom)
            parent: Parent item ID for creating sub-menu items

        Returns:
            JSON string with created menu item
        """
        try:
            data = {"menus": menu_id, "title": title, "type": type}

            if object_id:
                data["object_id"] = object_id
            if url:
                data["url"] = url
            if parent:
                data["parent"] = parent

            item = await self._make_request("POST", "menu-items", json_data=data)
            return self._format_success_response(item, "create_menu_item")
        except Exception as e:
            return self._format_error_response(e, "create_menu_item")

    async def update_menu_item(
        self,
        item_id: int,
        title: str | None = None,
        url: str | None = None,
        parent: int | None = None,
        menu_order: int | None = None,
    ) -> str:
        """
        Update an existing menu item.

        Args:
            item_id: Menu item ID
            title: New title
            url: New URL
            parent: New parent item ID
            menu_order: Position in menu

        Returns:
            JSON string with updated menu item
        """
        try:
            data = {}
            if title is not None:
                data["title"] = title
            if url is not None:
                data["url"] = url
            if parent is not None:
                data["parent"] = parent
            if menu_order is not None:
                data["menu_order"] = menu_order

            item = await self._make_request("PUT", f"menu-items/{item_id}", json_data=data)
            return self._format_success_response(item, "update_menu_item")
        except Exception as e:
            return self._format_error_response(e, "update_menu_item")

    # =========================================================================
    # Phase 6.2: Custom Post Types (4 tools)
    # =========================================================================

    async def list_post_types(self) -> str:
        """
        List all registered post types.

        Returns list of all post types including built-in (post, page)
        and custom post types (portfolio, testimonials, etc.).

        Returns:
            JSON string with total count and post types list

        Example response:
            {
              "total": 5,
              "post_types": [
                {
                  "slug": "portfolio",
                  "name": "Portfolio",
                  "rest_base": "portfolio",
                  "supports": ["title", "editor", "thumbnail"]
                }
              ]
            }
        """
        try:
            types_data = await self._make_request("GET", "types")

            # Convert dict to list
            post_types = []
            if isinstance(types_data, dict):
                for slug, data in types_data.items():
                    post_types.append(
                        {
                            "slug": slug,
                            "name": data.get("name", slug),
                            "description": data.get("description", ""),
                            "rest_base": data.get("rest_base", slug),
                            "hierarchical": data.get("hierarchical", False),
                            "supports": data.get("supports", {}),
                        }
                    )

            result = {"total": len(post_types), "post_types": post_types}
            return self._format_success_response(result, "list_post_types")
        except Exception as e:
            return self._format_error_response(e, "list_post_types")

    async def get_post_type_info(self, post_type: str) -> str:
        """
        Get detailed information about a specific post type.

        Args:
            post_type: Post type slug (e.g., 'portfolio', 'post', 'page')

        Returns:
            JSON string with post type details
        """
        try:
            info = await self._make_request("GET", f"types/{post_type}")
            return self._format_success_response(info, "get_post_type_info")
        except Exception as e:
            return self._format_error_response(e, "get_post_type_info")

    async def list_custom_posts(
        self, post_type: str, per_page: int = 10, page: int = 1, status: str = "any"
    ) -> str:
        """
        List posts of a specific custom post type.

        Args:
            post_type: Post type slug (e.g., 'portfolio', 'testimonials')
            per_page: Number of posts per page
            page: Page number
            status: Post status filter

        Returns:
            JSON string with posts list
        """
        try:
            params = {"per_page": per_page, "page": page, "status": status, "_embed": "true"}

            # Use the post type's rest_base as endpoint
            posts = await self._make_request("GET", post_type, params=params)

            result = {
                "total": len(posts) if isinstance(posts, list) else 0,
                "post_type": post_type,
                "page": page,
                "per_page": per_page,
                "posts": posts,
            }
            return self._format_success_response(result, "list_custom_posts")
        except Exception as e:
            return self._format_error_response(e, "list_custom_posts")

    async def create_custom_post(
        self,
        post_type: str,
        title: str,
        content: str,
        status: str = "draft",
        meta: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new post of a custom post type.

        Args:
            post_type: Post type slug (e.g., 'portfolio')
            title: Post title
            content: Post content (HTML allowed)
            status: Post status (draft, publish, etc.)
            meta: Custom fields/meta data

        Returns:
            JSON string with created post details
        """
        try:
            data = {"title": title, "content": content, "status": status}

            if meta:
                data["meta"] = meta

            post = await self._make_request("POST", post_type, json_data=data)
            return self._format_success_response(post, "create_custom_post")
        except Exception as e:
            return self._format_error_response(e, "create_custom_post")

    # =========================================================================
    # Phase 6.3: Custom Taxonomies (3 tools)
    # =========================================================================

    async def list_taxonomies(self) -> str:
        """
        List all registered taxonomies.

        Returns list of all taxonomies including built-in (category, post_tag)
        and custom taxonomies (portfolio_category, etc.).

        Returns:
            JSON string with total count and taxonomies list

        Example response:
            {
              "total": 4,
              "taxonomies": [
                {
                  "slug": "product_category",
                  "name": "Product Categories",
                  "types": ["product"],
                  "hierarchical": true
                }
              ]
            }
        """
        try:
            taxonomies_data = await self._make_request("GET", "taxonomies")

            # Convert dict to list
            taxonomies = []
            if isinstance(taxonomies_data, dict):
                for slug, data in taxonomies_data.items():
                    taxonomies.append(
                        {
                            "slug": slug,
                            "name": data.get("name", slug),
                            "description": data.get("description", ""),
                            "types": data.get("types", []),
                            "hierarchical": data.get("hierarchical", False),
                            "rest_base": data.get("rest_base", slug),
                        }
                    )

            result = {"total": len(taxonomies), "taxonomies": taxonomies}
            return self._format_success_response(result, "list_taxonomies")
        except Exception as e:
            return self._format_error_response(e, "list_taxonomies")

    async def list_taxonomy_terms(
        self,
        taxonomy: str,
        per_page: int = 100,
        page: int = 1,
        hide_empty: bool = False,
        parent: int | None = None,
    ) -> str:
        """
        List terms of a specific taxonomy.

        Args:
            taxonomy: Taxonomy slug (e.g., 'category', 'product_category')
            per_page: Number of terms per page
            page: Page number
            hide_empty: Hide terms with no posts
            parent: Filter by parent term ID

        Returns:
            JSON string with terms list
        """
        try:
            params = {"per_page": per_page, "page": page, "hide_empty": hide_empty}

            if parent is not None:
                params["parent"] = parent

            terms = await self._make_request("GET", taxonomy, params=params)

            result = {
                "total": len(terms) if isinstance(terms, list) else 0,
                "taxonomy": taxonomy,
                "page": page,
                "per_page": per_page,
                "terms": terms,
            }
            return self._format_success_response(result, "list_taxonomy_terms")
        except Exception as e:
            return self._format_error_response(e, "list_taxonomy_terms")

    async def create_taxonomy_term(
        self, taxonomy: str, name: str, description: str | None = None, parent: int | None = None
    ) -> str:
        """
        Create a new term in a taxonomy.

        Args:
            taxonomy: Taxonomy slug (e.g., 'category', 'product_category')
            name: Term name
            description: Term description
            parent: Parent term ID for hierarchical taxonomies

        Returns:
            JSON string with created term details
        """
        try:
            data = {"name": name}

            if description:
                data["description"] = description
            if parent:
                data["parent"] = parent

            term = await self._make_request("POST", taxonomy, json_data=data)
            return self._format_success_response(term, "create_taxonomy_term")
        except Exception as e:
            return self._format_error_response(e, "create_taxonomy_term")
