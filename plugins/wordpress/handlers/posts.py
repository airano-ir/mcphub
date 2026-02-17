"""Posts Handler - manages WordPress posts, pages, and custom post types"""

import asyncio
import json
import re
from typing import Any

from plugins.wordpress.client import WordPressClient

def _count_words(html_content: str) -> int:
    """Strip HTML tags and count words."""
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text.split()) if text else 0

def _strip_html(html_content: str, max_chars: int = 500) -> str:
    """Strip HTML tags and return first max_chars characters."""
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[:max_chars] + "..."
    return text

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === POSTS ===
        {
            "name": "list_posts",
            "method_name": "list_posts",
            "description": "List WordPress posts. Returns paginated list of posts with title, excerpt, status, and metadata.",
            "schema": {
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
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter posts",
                    },
                    "search_terms": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Multiple search terms to search in parallel. Results are deduplicated. Overrides 'search' if both provided.",
                    },
                    "include_content": {
                        "type": "boolean",
                        "description": "Include content summary (first 500 chars) and word count in results. Default false to save tokens.",
                        "default": False,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_post",
            "method_name": "get_post",
            "description": "Get a specific WordPress post by ID. Returns complete post data including content, metadata, and author information.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Post ID to retrieve",
                        "minimum": 1,
                    },
                    "fields": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated list of fields to return (e.g., 'id,title,status,tags'). Returns all fields if not specified. Use to reduce response size and token usage.",
                    },
                },
                "required": ["post_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_post",
            "method_name": "create_post",
            "description": "Create a new WordPress post. Supports custom slug, categories, tags, and featured image.",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Post title (displayed as main heading)",
                        "minLength": 1,
                    },
                    "content": {
                        "type": "string",
                        "description": "Post content (supports HTML and WordPress blocks)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Publication status",
                        "enum": ["publish", "draft", "pending", "private", "future"],
                        "default": "draft",
                    },
                    "slug": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Post URL slug (auto-generated from title if not provided)",
                    },
                    "excerpt": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Post excerpt/summary",
                    },
                    "categories": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Category IDs to assign to post",
                    },
                    "tags": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Tag IDs to assign to post",
                    },
                    "featured_media": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Featured image media ID",
                    },
                },
                "required": ["title", "content"],
            },
            "scope": "write",
        },
        {
            "name": "update_post",
            "method_name": "update_post",
            "description": "Update an existing WordPress post. Can update any field including title, content, status, categories, and tags.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Post ID to update",
                        "minimum": 1,
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Post title",
                    },
                    "content": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Post content",
                    },
                    "status": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Publication status",
                        "enum": ["publish", "draft", "pending", "private", "future"],
                    },
                    "slug": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Post URL slug",
                    },
                    "excerpt": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Post excerpt",
                    },
                    "categories": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Category IDs",
                    },
                    "tags": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Tag IDs",
                    },
                    "featured_media": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Featured image media ID",
                    },
                },
                "required": ["post_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_post",
            "method_name": "delete_post",
            "description": "Delete or trash a WordPress post. Can permanently delete or move to trash.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Post ID to delete",
                        "minimum": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Permanently delete (true) or move to trash (false)",
                        "default": False,
                    },
                },
                "required": ["post_id"],
            },
            "scope": "write",
        },
        # === PAGES ===
        {
            "name": "list_pages",
            "method_name": "list_pages",
            "description": "List WordPress pages. Returns paginated list of pages with metadata.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of pages per page (1-100)",
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
                        "description": "Filter by page status",
                        "enum": ["publish", "draft", "pending", "private", "any"],
                        "default": "any",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "create_page",
            "method_name": "create_page",
            "description": "Create a new WordPress page. Supports HTML content, parent pages, and custom slugs.",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Page title (displayed as main heading)",
                        "minLength": 1,
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
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Page URL slug (e.g., 'about-us'). Auto-generated from title if not provided.",
                    },
                    "parent": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Parent page ID for creating hierarchical page structure",
                    },
                },
                "required": ["title", "content"],
            },
            "scope": "write",
        },
        {
            "name": "update_page",
            "method_name": "update_page",
            "description": "Update an existing WordPress page. Can update title, content, status, slug, and parent page.",
            "schema": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "integer",
                        "description": "Page ID to update",
                        "minimum": 1,
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Page title",
                    },
                    "content": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Page content",
                    },
                    "status": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Publication status",
                        "enum": ["publish", "draft", "pending", "private"],
                    },
                    "slug": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Page URL slug",
                    },
                    "parent": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Parent page ID",
                    },
                },
                "required": ["page_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_page",
            "method_name": "delete_page",
            "description": "Delete or trash a WordPress page. Can permanently delete or move to trash.",
            "schema": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "integer",
                        "description": "Page ID to delete",
                        "minimum": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Permanently delete (true) or move to trash (false)",
                        "default": False,
                    },
                },
                "required": ["page_id"],
            },
            "scope": "write",
        },
        # === POST TYPES ===
        {
            "name": "list_post_types",
            "method_name": "list_post_types",
            "description": "List all registered post types including built-in (post, page) and custom post types (portfolio, testimonials, etc.).",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_post_type_info",
            "method_name": "get_post_type_info",
            "description": "Get detailed information about a specific post type including supported features and REST API configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_type": {
                        "type": "string",
                        "description": "Post type slug (e.g., 'portfolio', 'post', 'page')",
                    }
                },
                "required": ["post_type"],
            },
            "scope": "read",
        },
        # === CUSTOM POSTS ===
        {
            "name": "list_custom_posts",
            "method_name": "list_custom_posts",
            "description": "List posts of a specific custom post type. Use list_post_types first to discover available post types.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_type": {
                        "type": "string",
                        "description": "Post type slug (e.g., 'portfolio', 'testimonials')",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Number of posts per page",
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
                        "description": "Post status filter",
                        "enum": ["publish", "draft", "pending", "private", "any"],
                        "default": "any",
                    },
                },
                "required": ["post_type"],
            },
            "scope": "read",
        },
        {
            "name": "create_custom_post",
            "method_name": "create_custom_post",
            "description": "Create a new post of a custom post type. Supports custom fields/meta data.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_type": {
                        "type": "string",
                        "description": "Post type slug (e.g., 'portfolio')",
                    },
                    "title": {"type": "string", "description": "Post title", "minLength": 1},
                    "content": {"type": "string", "description": "Post content (HTML allowed)"},
                    "status": {
                        "type": "string",
                        "description": "Post status",
                        "enum": ["publish", "draft", "pending", "private", "future"],
                        "default": "draft",
                    },
                    "meta": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Custom fields/meta data",
                    },
                },
                "required": ["post_type", "title", "content"],
            },
            "scope": "write",
        },
        # === INTERNAL LINKS ===
        {
            "name": "get_internal_links",
            "method_name": "get_internal_links",
            "description": "Extract internal links from a post's content. Returns list of internal links with anchor text and URL. Useful for SEO internal linking analysis and avoiding duplicate links.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Post ID to analyze for internal links",
                        "minimum": 1,
                    }
                },
                "required": ["post_id"],
            },
            "scope": "read",
        },
    ]

class PostsHandler:
    """Handle post-related operations for WordPress"""

    def __init__(self, client: WordPressClient):
        """
        Initialize posts handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    # === POSTS ===

    async def list_posts(
        self,
        per_page: int = 10,
        page: int = 1,
        status: str = "any",
        search: str | None = None,
        search_terms: list[str] | None = None,
        include_content: bool = False,
    ) -> str:
        """
        List WordPress posts.

        Args:
            per_page: Number of posts per page (1-100)
            page: Page number
            status: Post status filter (publish, draft, pending, private, any)
            search: Search term to filter posts
            search_terms: Multiple search terms for parallel search with deduplication
            include_content: Include content summary and word count in results

        Returns:
            JSON string with posts list
        """
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "status": status,
                "_embed": "true",  # Include author and featured image
            }

            # Multi-search: parallel API calls with deduplication
            if search_terms and len(search_terms) > 0:

                async def _search_single(term: str) -> list:
                    p = {**params, "search": term}
                    return await self.client.get("posts", params=p)

                batches = await asyncio.gather(
                    *[_search_single(term) for term in search_terms], return_exceptions=True
                )
                seen_ids: set = set()
                posts: list = []
                for batch in batches:
                    if isinstance(batch, Exception):
                        continue
                    for post in batch:
                        if post["id"] not in seen_ids:
                            seen_ids.add(post["id"])
                            posts.append(post)
            else:
                if search:
                    params["search"] = search
                posts = await self.client.get("posts", params=params)

            # Format response
            def _format_post(post: dict) -> dict:
                item = {
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
                if include_content:
                    content_html = post.get("content", {}).get("rendered", "")
                    item["content_summary"] = _strip_html(content_html, 500)
                    item["word_count"] = _count_words(content_html)
                return item

            result = {
                "total": len(posts),
                "page": page,
                "per_page": per_page,
                "posts": [_format_post(post) for post in posts],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list posts: {str(e)}"}, indent=2
            )

    async def get_post(self, post_id: int, fields: str | None = None) -> str:
        """
        Get a specific WordPress post.

        Args:
            post_id: Post ID to retrieve
            fields: Comma-separated list of fields to return (e.g., 'id,title,status')

        Returns:
            JSON string with post data
        """
        try:
            params = {"_embed": "true"}
            if fields:
                # Map our field names to WordPress API _fields
                wp_fields = set()
                requested = {f.strip().lower() for f in fields.split(",")}
                field_map = {
                    "id": "id",
                    "title": "title",
                    "content": "content",
                    "excerpt": "excerpt",
                    "status": "status",
                    "date": "date",
                    "modified": "modified",
                    "author": "_embedded",
                    "categories": "categories",
                    "tags": "tags",
                    "link": "link",
                    "slug": "slug",
                }
                for f in requested:
                    if f in field_map:
                        wp_fields.add(field_map[f])
                # Always include id and title for basic identification
                wp_fields.update({"id", "title"})
                params["_fields"] = ",".join(wp_fields)

            post = await self.client.get(f"posts/{post_id}", params=params)

            # Build full result
            full_result = {
                "id": post["id"],
                "title": post.get("title", {}).get("rendered", ""),
                "content": post.get("content", {}).get("rendered", ""),
                "excerpt": post.get("excerpt", {}).get("rendered", ""),
                "status": post.get("status", ""),
                "date": post.get("date", ""),
                "modified": post.get("modified", ""),
                "author": post.get("_embedded", {}).get("author", [{}])[0].get("name", "Unknown"),
                "categories": post.get("categories", []),
                "tags": post.get("tags", []),
                "link": post.get("link", ""),
                "word_count": _count_words(post.get("content", {}).get("rendered", "")),
            }

            # Filter to requested fields only
            if fields:
                requested = {f.strip().lower() for f in fields.split(",")}
                # Always include id
                requested.add("id")
                result = {k: v for k, v in full_result.items() if k in requested}
            else:
                result = full_result

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get post {post_id}: {str(e)}"}, indent=2
            )

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
        """
        Create a new WordPress post.

        Args:
            title: Post title
            content: Post content (HTML allowed)
            status: Publication status (draft, publish, pending, private, future)
            slug: Post URL slug (auto-generated if not provided)
            excerpt: Post excerpt/summary
            categories: Category IDs to assign
            tags: Tag IDs to assign
            featured_media: Featured image media ID

        Returns:
            JSON string with created post data
        """
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

            post = await self.client.post("posts", json_data=data)

            result = {
                "id": post["id"],
                "title": post["title"]["rendered"],
                "status": post["status"],
                "link": post["link"],
                "message": f"Post created successfully with ID {post['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create post: {str(e)}"}, indent=2
            )

    async def update_post(
        self,
        post_id: int,
        title: str | None = None,
        content: str | None = None,
        status: str | None = None,
        slug: str | None = None,
        excerpt: str | None = None,
        categories: list[int] | None = None,
        tags: list[int] | None = None,
        featured_media: int | None = None,
    ) -> str:
        """
        Update an existing WordPress post.

        Args:
            post_id: Post ID to update
            title: Post title
            content: Post content
            status: Publication status
            slug: Post URL slug
            excerpt: Post excerpt
            categories: Category IDs
            tags: Tag IDs
            featured_media: Featured image media ID

        Returns:
            JSON string with updated post data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if title is not None:
                data["title"] = title
            if content is not None:
                data["content"] = content
            if status is not None:
                data["status"] = status
            if slug is not None:
                data["slug"] = slug
            if excerpt is not None:
                data["excerpt"] = excerpt
            if categories is not None:
                data["categories"] = categories
            if tags is not None:
                data["tags"] = tags
            if featured_media is not None:
                data["featured_media"] = featured_media

            post = await self.client.post(f"posts/{post_id}", json_data=data)

            result = {
                "id": post["id"],
                "title": post["title"]["rendered"],
                "status": post["status"],
                "link": post["link"],
                "message": f"Post {post_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update post {post_id}: {str(e)}"}, indent=2
            )

    async def delete_post(self, post_id: int, force: bool = False) -> str:
        """
        Delete or trash a WordPress post.

        Args:
            post_id: Post ID to delete
            force: Permanently delete (True) or move to trash (False)

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"force": "true" if force else "false"}
            result = await self.client.delete(f"posts/{post_id}", params=params)

            message = f"Post {post_id} {'permanently deleted' if force else 'moved to trash'}"
            return json.dumps({"success": True, "message": message, "result": result}, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete post {post_id}: {str(e)}"}, indent=2
            )

    # === PAGES ===

    async def list_pages(self, per_page: int = 10, page: int = 1, status: str = "any") -> str:
        """
        List WordPress pages.

        Args:
            per_page: Number of pages per page (1-100)
            page: Page number
            status: Page status filter

        Returns:
            JSON string with pages list
        """
        try:
            params = {"per_page": per_page, "page": page, "status": status}
            pages = await self.client.get("pages", params=params)

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

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list pages: {str(e)}"}, indent=2
            )

    async def create_page(
        self,
        title: str,
        content: str,
        status: str = "draft",
        slug: str | None = None,
        parent: int | None = None,
    ) -> str:
        """
        Create a new WordPress page.

        Args:
            title: Page title
            content: Page content (HTML allowed)
            status: Publication status (draft, publish, pending, private)
            slug: Page URL slug (auto-generated if not provided)
            parent: Parent page ID for hierarchical structure

        Returns:
            JSON string with created page data
        """
        try:
            data = {"title": title, "content": content, "status": status}
            if slug:
                data["slug"] = slug
            if parent:
                data["parent"] = parent

            page = await self.client.post("pages", json_data=data)

            result = {
                "id": page["id"],
                "title": page["title"]["rendered"],
                "status": page["status"],
                "link": page["link"],
                "message": f"Page created successfully with ID {page['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create page: {str(e)}"}, indent=2
            )

    async def update_page(
        self,
        page_id: int,
        title: str | None = None,
        content: str | None = None,
        status: str | None = None,
        slug: str | None = None,
        parent: int | None = None,
    ) -> str:
        """
        Update an existing WordPress page.

        Args:
            page_id: Page ID to update
            title: Page title
            content: Page content
            status: Publication status
            slug: Page URL slug
            parent: Parent page ID

        Returns:
            JSON string with updated page data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if title is not None:
                data["title"] = title
            if content is not None:
                data["content"] = content
            if status is not None:
                data["status"] = status
            if slug is not None:
                data["slug"] = slug
            if parent is not None:
                data["parent"] = parent

            page = await self.client.post(f"pages/{page_id}", json_data=data)

            result = {
                "id": page["id"],
                "title": page["title"]["rendered"],
                "status": page["status"],
                "link": page["link"],
                "message": f"Page {page_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update page {page_id}: {str(e)}"}, indent=2
            )

    async def delete_page(self, page_id: int, force: bool = False) -> str:
        """
        Delete or trash a WordPress page.

        Args:
            page_id: Page ID to delete
            force: Permanently delete (True) or move to trash (False)

        Returns:
            JSON string with deletion result
        """
        try:
            # Phase K.2.4: Convert boolean to string for WP REST API
            params = {"force": "true" if force else "false"}
            await self.client.delete(f"pages/{page_id}", params=params)

            if force:
                message = f"Page {page_id} permanently deleted"
            else:
                message = f"Page {page_id} moved to trash"

            result = {"id": page_id, "deleted": True, "force": force, "message": message}

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete page {page_id}: {str(e)}"}, indent=2
            )

    # === POST TYPES ===

    async def list_post_types(self) -> str:
        """
        List all registered post types.

        Returns list of all post types including built-in (post, page)
        and custom post types (portfolio, testimonials, etc.).

        Returns:
            JSON string with total count and post types list
        """
        try:
            types_data = await self.client.get("types")

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

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list post types: {str(e)}"}, indent=2
            )

    async def get_post_type_info(self, post_type: str) -> str:
        """
        Get detailed information about a specific post type.

        Args:
            post_type: Post type slug (e.g., 'portfolio', 'post', 'page')

        Returns:
            JSON string with post type details
        """
        try:
            info = await self.client.get(f"types/{post_type}")
            return json.dumps(info, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to get post type info for '{post_type}': {str(e)}",
                },
                indent=2,
            )

    # === CUSTOM POSTS ===

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
            posts = await self.client.get(post_type, params=params)

            result = {
                "total": len(posts) if isinstance(posts, list) else 0,
                "post_type": post_type,
                "page": page,
                "per_page": per_page,
                "posts": posts,
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to list custom posts of type '{post_type}': {str(e)}",
                },
                indent=2,
            )

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

            post = await self.client.post(post_type, json_data=data)

            return json.dumps(post, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to create custom post of type '{post_type}': {str(e)}",
                },
                indent=2,
            )

    # === INTERNAL LINKS ===

    async def get_internal_links(self, post_id: int) -> str:
        """
        Extract internal links from a post's content.

        Args:
            post_id: Post ID to analyze

        Returns:
            JSON string with internal and external link counts
        """
        try:
            post = await self.client.get(
                f"posts/{post_id}", params={"_fields": "id,title,content,link"}
            )

            content_html = post.get("content", {}).get("rendered", "")
            post_title = post.get("title", {}).get("rendered", "")
            post_link = post.get("link", "")

            # Extract site URL from post link
            from urllib.parse import urlparse

            parsed = urlparse(post_link)
            site_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else ""

            # Extract all <a> tags with href and anchor text
            link_pattern = re.compile(
                r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )
            matches = link_pattern.findall(content_html)

            internal_links = []
            external_count = 0

            for href, anchor_html in matches:
                anchor_text = re.sub(r"<[^>]+>", "", anchor_html).strip()
                href = href.strip()

                # Skip anchors and empty hrefs
                if not href or href.startswith("#") or href.startswith("mailto:"):
                    continue

                # Check if internal
                is_internal = False
                if site_url and href.startswith(site_url):
                    is_internal = True
                elif href.startswith("/") and not href.startswith("//"):
                    is_internal = True
                    href = site_url + href

                if is_internal:
                    internal_links.append(
                        {
                            "url": href,
                            "anchor_text": anchor_text,
                        }
                    )
                else:
                    external_count += 1

            result = {
                "post_id": post_id,
                "post_title": post_title,
                "site_url": site_url,
                "total_internal_links": len(internal_links),
                "internal_links": internal_links,
                "external_links_count": external_count,
            }

            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to get internal links for post {post_id}: {str(e)}",
                },
                indent=2,
            )
