"""Media Handler - manages WordPress media library operations"""

import json
from typing import Any

import aiohttp

from plugins.wordpress.client import WordPressClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === MEDIA ===
        {
            "name": "list_media",
            "method_name": "list_media",
            "description": "List media library items. Returns images, videos, documents with URLs and metadata.",
            "schema": {
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
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter by media type (image, video, audio, or application)",
                        "enum": ["image", "video", "audio", "application"],
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_media",
            "method_name": "get_media",
            "description": "Get detailed information about a media item. Returns full metadata including URLs, dimensions, and MIME type.",
            "schema": {
                "type": "object",
                "properties": {
                    "media_id": {
                        "type": "integer",
                        "description": "Media ID to retrieve",
                        "minimum": 1,
                    }
                },
                "required": ["media_id"],
            },
            "scope": "read",
        },
        {
            "name": "upload_media_from_url",
            "method_name": "upload_media_from_url",
            "description": "Upload media from URL to media library (sideload). Downloads file from public URL and uploads to WordPress.",
            "schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Public URL of the media file to upload (image, video, document, etc.)",
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media title (used in media library)",
                    },
                    "alt_text": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Alternative text for accessibility (important for images)",
                    },
                    "caption": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media caption (displayed below image when inserted into content)",
                    },
                },
                "required": ["url"],
            },
            "scope": "write",
        },
        {
            "name": "update_media",
            "method_name": "update_media",
            "description": "Update media metadata. Supports title, description, slug, alt text, caption, status, and associated post.",
            "schema": {
                "type": "object",
                "properties": {
                    "media_id": {
                        "type": "integer",
                        "description": "Media ID to update",
                        "minimum": 1,
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media title (displayed in media library)",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media description (full text content, displayed in attachment page)",
                    },
                    "slug": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media URL slug (e.g., 'my-image-name')",
                    },
                    "alt_text": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Alternative text for accessibility (important for images)",
                    },
                    "caption": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media caption (shown below image in content)",
                    },
                    "status": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Publication status of the media",
                        "enum": ["publish", "draft", "private"],
                    },
                    "post": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "ID of the post/page to attach this media to",
                    },
                },
                "required": ["media_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_media",
            "method_name": "delete_media",
            "description": "Delete media from library. Can permanently delete or move to trash.",
            "schema": {
                "type": "object",
                "properties": {
                    "media_id": {
                        "type": "integer",
                        "description": "Media ID to delete",
                        "minimum": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Permanently delete (true) or move to trash (false)",
                        "default": False,
                    },
                },
                "required": ["media_id"],
            },
            "scope": "write",
        },
    ]

class MediaHandler:
    """Handle media-related operations for WordPress"""

    def __init__(self, client: WordPressClient):
        """
        Initialize media handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    # === MEDIA ===

    async def list_media(
        self, per_page: int = 20, page: int = 1, media_type: str | None = None
    ) -> str:
        """
        List media library items.

        Args:
            per_page: Number of media items per page (1-100)
            page: Page number
            media_type: Filter by media type (image, video, audio, application)

        Returns:
            JSON string with media list
        """
        try:
            params = {"per_page": per_page, "page": page}
            if media_type:
                params["media_type"] = media_type

            media = await self.client.get("media", params=params)

            # Format response
            result = {
                "total": len(media),
                "page": page,
                "per_page": per_page,
                "media": [
                    {
                        "id": m["id"],
                        "title": m["title"]["rendered"],
                        "mime_type": m["mime_type"],
                        "media_type": m.get("media_type", ""),
                        "url": m["source_url"],
                        "date": m["date"],
                        "alt_text": m.get("alt_text", ""),
                        "link": m.get("link", ""),
                    }
                    for m in media
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list media: {str(e)}"}, indent=2
            )

    async def get_media(self, media_id: int) -> str:
        """
        Get detailed information about a specific media item.

        Args:
            media_id: Media ID to retrieve

        Returns:
            JSON string with media data
        """
        try:
            media = await self.client.get(f"media/{media_id}")

            result = {
                "id": media["id"],
                "title": media["title"]["rendered"],
                "mime_type": media["mime_type"],
                "media_type": media.get("media_type", ""),
                "url": media["source_url"],
                "alt_text": media.get("alt_text", ""),
                "caption": media.get("caption", {}).get("rendered", ""),
                "description": media.get("description", {}).get("rendered", ""),
                "date": media["date"],
                "modified": media.get("modified", ""),
                "link": media.get("link", ""),
                "media_details": media.get("media_details", {}),
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get media {media_id}: {str(e)}"}, indent=2
            )

    async def upload_media_from_url(
        self,
        url: str,
        title: str | None = None,
        alt_text: str | None = None,
        caption: str | None = None,
    ) -> str:
        """
        Upload media from URL to media library (sideload).

        Downloads file from a public URL and uploads it to WordPress media library.

        Args:
            url: Public URL of the media file to upload
            title: Media title (used in media library)
            alt_text: Alternative text for accessibility
            caption: Media caption (displayed below image)

        Returns:
            JSON string with uploaded media data
        """
        try:
            # Download file from URL
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                if response.status >= 400:
                    raise Exception(f"Failed to download from URL: HTTP {response.status}")

                file_content = await response.read()
                content_type = response.headers.get("Content-Type", "application/octet-stream")

                # Extract filename from URL
                filename = url.split("/")[-1].split("?")[0]
                if not filename:
                    filename = "downloaded_file"

            # Create FormData for upload
            form = aiohttp.FormData()
            form.add_field("file", file_content, filename=filename, content_type=content_type)

            # Upload to WordPress using client's upload method
            # Note: We need to use the client's base_url and auth directly for file upload
            upload_url = f"{self.client.base_url}/media"
            headers = {
                "Authorization": self.client.auth_header,
                "Content-Disposition": f'attachment; filename="{filename}"',
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(upload_url, data=form, headers=headers) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"Upload failed (HTTP {response.status}): {error_text}")

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

                await self.client.post(f"media/{media['id']}", json_data=update_data)

            result = {
                "id": media["id"],
                "title": media["title"]["rendered"],
                "url": media["source_url"],
                "mime_type": media["mime_type"],
                "message": f"Media uploaded from URL successfully with ID {media['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to upload media from URL: {str(e)}"}, indent=2
            )

    async def update_media(
        self,
        media_id: int,
        title: str | None = None,
        description: str | None = None,
        slug: str | None = None,
        alt_text: str | None = None,
        caption: str | None = None,
        status: str | None = None,
        post: int | None = None,
    ) -> str:
        """
        Update media metadata.

        Args:
            media_id: Media ID to update
            title: Media title
            description: Media description
            slug: Media URL slug
            alt_text: Alternative text for accessibility
            caption: Media caption
            status: Publication status (publish, draft, private)
            post: ID of post/page to attach media to

        Returns:
            JSON string with updated media data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if title is not None:
                data["title"] = title
            if description is not None:
                data["description"] = description
            if slug is not None:
                data["slug"] = slug
            if alt_text is not None:
                data["alt_text"] = alt_text
            if caption is not None:
                data["caption"] = caption
            if status is not None:
                data["status"] = status
            if post is not None:
                data["post"] = post

            media = await self.client.post(f"media/{media_id}", json_data=data)

            result = {
                "id": media["id"],
                "title": media["title"]["rendered"],
                "alt_text": media.get("alt_text", ""),
                "caption": media.get("caption", {}).get("rendered", ""),
                "url": media["source_url"],
                "message": f"Media {media_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update media {media_id}: {str(e)}"},
                indent=2,
            )

    async def delete_media(self, media_id: int, force: bool = False) -> str:
        """
        Delete or trash media from library.

        Args:
            media_id: Media ID to delete
            force: Permanently delete (True) or move to trash (False)

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"force": "true" if force else "false"}
            result = await self.client.delete(f"media/{media_id}", params=params)

            message = f"Media {media_id} {'permanently deleted' if force else 'moved to trash'}"
            return json.dumps({"success": True, "message": message, "result": result}, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete media {media_id}: {str(e)}"},
                indent=2,
            )
