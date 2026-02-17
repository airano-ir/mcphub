"""Comments Handler - manages WordPress comments and moderation"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === COMMENTS ===
        {
            "name": "list_comments",
            "method_name": "list_comments",
            "description": "List WordPress comments. Returns paginated list of comments with author, content, and moderation status.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of comments per page (1-100)",
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
                    "post_id": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Filter by post ID (optional)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by comment status",
                        "enum": ["approve", "hold", "spam", "trash", "all"],
                        "default": "approve",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_comment",
            "method_name": "get_comment",
            "description": "Get a specific WordPress comment by ID. Returns complete comment data including content, author, and moderation status.",
            "schema": {
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "integer",
                        "description": "Comment ID to retrieve",
                        "minimum": 1,
                    }
                },
                "required": ["comment_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_comment",
            "method_name": "create_comment",
            "description": "Create a new WordPress comment on a post. Supports author information and moderation status.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Post ID to attach comment to",
                        "minimum": 1,
                    },
                    "content": {
                        "type": "string",
                        "description": "Comment content/text",
                        "minLength": 1,
                    },
                    "author_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Author name (for unauthenticated comments)",
                    },
                    "author_email": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Author email address",
                    },
                    "status": {
                        "type": "string",
                        "description": "Comment moderation status",
                        "enum": ["approve", "hold", "spam"],
                        "default": "hold",
                    },
                },
                "required": ["post_id", "content"],
            },
            "scope": "write",
        },
        {
            "name": "update_comment",
            "method_name": "update_comment",
            "description": "Update an existing WordPress comment. Can update content, status, author information, etc.",
            "schema": {
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "integer",
                        "description": "Comment ID to update",
                        "minimum": 1,
                    },
                    "content": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comment content/text",
                    },
                    "author_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Author name",
                    },
                    "author_email": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Author email",
                    },
                    "status": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comment moderation status",
                        "enum": ["approve", "hold", "spam"],
                    },
                },
                "required": ["comment_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_comment",
            "method_name": "delete_comment",
            "description": "Delete or trash a WordPress comment. Can permanently delete or move to trash.",
            "schema": {
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "integer",
                        "description": "Comment ID to delete",
                        "minimum": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Permanently delete (true) or move to trash (false)",
                        "default": False,
                    },
                },
                "required": ["comment_id"],
            },
            "scope": "write",
        },
    ]

class CommentsHandler:
    """Handle comment-related operations for WordPress"""

    def __init__(self, client: WordPressClient):
        """
        Initialize comments handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    async def list_comments(
        self, per_page: int = 10, page: int = 1, post_id: int | None = None, status: str = "approve"
    ) -> str:
        """
        List WordPress comments.

        Args:
            per_page: Number of comments per page (1-100)
            page: Page number
            post_id: Optional filter by post ID
            status: Comment status filter (approve, hold, spam, trash, all)

        Returns:
            JSON string with comments list
        """
        try:
            params = {"per_page": per_page, "page": page, "status": status}
            if post_id:
                params["post"] = post_id

            comments = await self.client.get("comments", params=params)

            # Format response
            result = {
                "total": len(comments),
                "page": page,
                "per_page": per_page,
                "comments": [
                    {
                        "id": c["id"],
                        "post_id": c["post"],
                        "author_name": c["author_name"],
                        "author_email": c.get("author_email", ""),
                        "content": c["content"]["rendered"][:200],
                        "status": c["status"],
                        "date": c["date"],
                        "link": c.get("link", ""),
                    }
                    for c in comments
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list comments: {str(e)}"}, indent=2
            )

    async def get_comment(self, comment_id: int) -> str:
        """
        Get a specific WordPress comment.

        Args:
            comment_id: Comment ID to retrieve

        Returns:
            JSON string with comment data
        """
        try:
            comment = await self.client.get(f"comments/{comment_id}")

            result = {
                "id": comment["id"],
                "post_id": comment["post"],
                "author_name": comment["author_name"],
                "author_email": comment.get("author_email", ""),
                "author_url": comment.get("author_url", ""),
                "content": comment["content"]["rendered"],
                "status": comment["status"],
                "date": comment["date"],
                "link": comment.get("link", ""),
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get comment {comment_id}: {str(e)}"},
                indent=2,
            )

    async def create_comment(
        self,
        post_id: int,
        content: str,
        author_name: str | None = None,
        author_email: str | None = None,
        status: str = "hold",
    ) -> str:
        """
        Create a new WordPress comment.

        Args:
            post_id: Post ID to attach comment to
            content: Comment content/text
            author_name: Author name (for unauthenticated comments)
            author_email: Author email address
            status: Comment moderation status (approve, hold, spam)

        Returns:
            JSON string with created comment data
        """
        try:
            data = {"post": post_id, "content": content, "status": status}
            if author_name:
                data["author_name"] = author_name
            if author_email:
                data["author_email"] = author_email

            comment = await self.client.post("comments", json_data=data)

            result = {
                "id": comment["id"],
                "post_id": comment["post"],
                "author_name": comment["author_name"],
                "content": comment["content"]["rendered"],
                "status": comment["status"],
                "message": f"Comment created successfully with ID {comment['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create comment: {str(e)}"}, indent=2
            )

    async def update_comment(
        self,
        comment_id: int,
        content: str | None = None,
        author_name: str | None = None,
        author_email: str | None = None,
        status: str | None = None,
    ) -> str:
        """
        Update an existing WordPress comment.

        Args:
            comment_id: Comment ID to update
            content: Comment content/text
            author_name: Author name
            author_email: Author email
            status: Comment moderation status

        Returns:
            JSON string with updated comment data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if content is not None:
                data["content"] = content
            if author_name is not None:
                data["author_name"] = author_name
            if author_email is not None:
                data["author_email"] = author_email
            if status is not None:
                data["status"] = status

            comment = await self.client.post(f"comments/{comment_id}", json_data=data)

            result = {
                "id": comment["id"],
                "post_id": comment["post"],
                "content": comment["content"]["rendered"],
                "status": comment["status"],
                "message": f"Comment {comment_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update comment {comment_id}: {str(e)}"},
                indent=2,
            )

    async def delete_comment(self, comment_id: int, force: bool = False) -> str:
        """
        Delete or trash a WordPress comment.

        Args:
            comment_id: Comment ID to delete
            force: Permanently delete (True) or move to trash (False)

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"force": "true" if force else "false"}
            result = await self.client.delete(f"comments/{comment_id}", params=params)

            message = f"Comment {comment_id} {'permanently deleted' if force else 'moved to trash'}"
            return json.dumps({"success": True, "message": message, "result": result}, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete comment {comment_id}: {str(e)}"},
                indent=2,
            )
