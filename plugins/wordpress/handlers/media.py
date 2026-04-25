"""Media Handler - manages WordPress media library operations"""

import base64 as _b64
import binascii
import json
from typing import Any

from core.media_audit import log_media_upload
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._media_core import (
    fetch_url_bytes,
    wp_raw_upload,
    wp_set_featured_media,
    wp_update_media_metadata,
)
from plugins.wordpress.handlers._media_security import (
    DEFAULT_MAX_BYTES,
    UploadError,
    ssrf_check,
)


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
            "description": "Upload media from a public URL to the WordPress media library (sideload). Downloads the file with SSRF protection, sniffs MIME, and uploads via raw-binary POST.",
            "schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Public HTTPS URL of the media file",
                    },
                    "filename": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Override filename (default: derived from URL)",
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media title (used in media library)",
                    },
                    "alt_text": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Alternative text for accessibility",
                    },
                    "caption": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media caption",
                    },
                    "attach_to_post": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Attach uploaded media to this post/page ID",
                    },
                    "set_featured": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true and attach_to_post is set, also set as the post's featured image",
                    },
                    "skip_optimize": {
                        "type": "boolean",
                        "default": False,
                        "description": "Skip server-side image optimization (F.5a.2)",
                    },
                    "convert_to": {
                        "anyOf": [{"type": "string", "enum": ["webp", "avif"]}, {"type": "null"}],
                        "description": (
                            "F.5a.8.1: re-encode the image in a modern format before upload. "
                            "'webp' or 'avif'. Falls back to WebP if AVIF is unavailable. "
                            "Leave null to keep source format (or use WP_MEDIA_CONVERT_TO env default)."
                        ),
                    },
                },
                "required": ["url"],
            },
            "scope": "write",
        },
        {
            "name": "upload_media_from_base64",
            "method_name": "upload_media_from_base64",
            "description": "Upload a base64-encoded file directly to the WordPress media library. For chat-attached images/files smaller than ~10 MB. Use upload_media_from_url for larger files or chunked path later.",
            "schema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "Base64-encoded file bytes (no data: URL prefix required; prefix will be stripped if present)",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Filename including extension (e.g. 'cover.jpg')",
                    },
                    "mime": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Client-supplied MIME hint; ignored if magic-byte sniff says otherwise",
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Media title",
                    },
                    "alt_text": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Alternative text",
                    },
                    "caption": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Caption",
                    },
                    "attach_to_post": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Attach to this post/page ID",
                    },
                    "set_featured": {
                        "type": "boolean",
                        "default": False,
                        "description": "Also set as the post's featured image",
                    },
                    "skip_optimize": {
                        "type": "boolean",
                        "default": False,
                        "description": "Skip server-side image optimization",
                    },
                    "convert_to": {
                        "anyOf": [{"type": "string", "enum": ["webp", "avif"]}, {"type": "null"}],
                        "description": (
                            "F.5a.8.1: re-encode the image in a modern format before upload. "
                            "'webp' or 'avif'. Falls back to WebP if AVIF is unavailable."
                        ),
                    },
                },
                "required": ["data", "filename"],
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


def _decode_base64(data: str) -> bytes:
    """Accept raw base64 or data: URL prefix; return decoded bytes."""
    s = (data or "").strip()
    if s.startswith("data:") and "," in s:
        s = s.split(",", 1)[1]
    s = s.replace("\n", "").replace("\r", "").replace(" ", "")
    try:
        return _b64.b64decode(s, validate=True)
    except (binascii.Error, ValueError) as e:
        raise UploadError("BAD_BASE64", f"Invalid base64 payload: {e}") from e


def _maybe_optimize(
    data: bytes,
    mime_hint: str | None,
    *,
    skip: bool,
    convert_to: str | None = None,
) -> tuple[bytes, str | None]:
    """Route image bytes through the F.5a.2 optimize pipeline.

    F.5a.8.1: ``convert_to`` is forwarded to the optimizer so callers can
    force WebP/AVIF output. A falsy value defers to the ``WP_MEDIA_CONVERT_TO``
    env var.
    """
    if skip:
        return data, mime_hint
    try:
        from plugins.wordpress.handlers._media_optimize import optimize  # type: ignore
    except ImportError:
        return data, mime_hint
    return optimize(data, mime_hint, convert_to=convert_to)


async def _apply_metadata_and_attach(
    client: WordPressClient,
    media: dict[str, Any],
    *,
    title: str | None,
    alt_text: str | None,
    caption: str | None,
    attach_to_post: int | None,
    set_featured: bool,
    wc_client: WordPressClient | None = None,
) -> dict[str, Any]:
    """Apply metadata + attach to post / featured-image.

    F.5a.8.5 — when the companion's single-call ``upload-and-attach``
    route already applied these fields, skip everything (saves 1-2
    redundant round-trips).

    F.X.fix-pass6 — return a status dict so callers can surface
    "media uploaded but featured failed" as partial success instead
    of a misleading GENERATION_FAILED. When ``set_featured`` targets
    a WooCommerce product (CPT, not addressable via /wp/v2/posts/{id}),
    route through the WC products endpoint via ``wc_client``. Both
    "metadata applied" and "featured set" steps are reported
    independently in the result dict.
    """
    status: dict[str, Any] = {
        "metadata_applied": False,
        "featured_set": False,
        "featured_context": None,
        "warnings": [],
    }
    if media.get("_upload_route") == "companion_unified":
        # Companion did metadata + attach + featured atomically.
        status["metadata_applied"] = True
        status["featured_set"] = bool(set_featured and attach_to_post)
        status["featured_context"] = "companion_unified"
        return status

    if any(v is not None for v in (title, alt_text, caption)) or attach_to_post is not None:
        try:
            await wp_update_media_metadata(
                client,
                media["id"],
                title=title,
                alt_text=alt_text,
                caption=caption,
                post=attach_to_post,
            )
            status["metadata_applied"] = True
        except Exception as exc:  # noqa: BLE001
            status["warnings"].append(f"metadata_failed: {exc}")

    if set_featured and attach_to_post is not None:
        # 1. WC product first (CPT). Falls through to /wp/v2/posts on miss.
        wc = wc_client or client
        wc_product = None
        try:
            wc_product = await wc.get(f"products/{attach_to_post}", use_woocommerce=True)
        except Exception:
            wc_product = None

        if isinstance(wc_product, dict) and wc_product.get("id"):
            try:
                existing_images = list(wc_product.get("images") or [])
                # Featured = images[0]; preserve gallery via the same
                # merge primitive used by attach_media_to_product.
                from plugins.wordpress.handlers.media_attach import _merge_product_images

                new_images = _merge_product_images(
                    existing=existing_images,
                    new_ids=[media["id"]],
                    role="main",
                    mode="replace",
                )
                await wc.put(
                    f"products/{attach_to_post}",
                    json_data={"images": new_images},
                    use_woocommerce=True,
                )
                status["featured_set"] = True
                status["featured_context"] = "product"
            except Exception as exc:  # noqa: BLE001
                status["warnings"].append(f"featured_set_failed (product): {exc}")
        else:
            try:
                await wp_set_featured_media(client, attach_to_post, media["id"])
                status["featured_set"] = True
                status["featured_context"] = "post"
            except Exception as exc:  # noqa: BLE001
                status["warnings"].append(f"featured_set_failed (post): {exc}")

    return status


def _format_upload_result(media: dict[str, Any], *, source: str) -> dict[str, Any]:
    title = media.get("title")
    rendered_title = title.get("rendered") if isinstance(title, dict) else title
    return {
        "id": media["id"],
        "title": rendered_title or "",
        "url": media.get("source_url", ""),
        "mime_type": media.get("mime_type", ""),
        "media_type": media.get("media_type", ""),
        "size_bytes": media.get("media_details", {}).get("filesize"),
        "source": source,
        "message": f"Media uploaded successfully (id={media['id']}).",
    }


class MediaHandler:
    """Handle media-related operations for WordPress"""

    def __init__(self, client: WordPressClient, *, user_id: str | None = None):
        """
        Initialize media handler.

        Args:
            client: WordPress API client instance
            user_id: Calling user id, used for audit logging (None = admin/env)
        """
        self.client = client
        self.user_id = user_id

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
                        # F.X.fix #6: expose post_parent so callers can
                        # verify "is media X attached to post Y" without
                        # a second WP REST round trip. WP returns 0 for
                        # unattached media; we preserve that.
                        "post_parent": m.get("post") or 0,
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
                # F.X.fix #6: expose post_parent so attach-verification
                # doesn't need a second round trip via posts/{id}.
                "post_parent": media.get("post") or 0,
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get media {media_id}: {str(e)}"}, indent=2
            )

    async def upload_media_from_url(
        self,
        url: str,
        filename: str | None = None,
        title: str | None = None,
        alt_text: str | None = None,
        caption: str | None = None,
        attach_to_post: int | None = None,
        set_featured: bool = False,
        skip_optimize: bool = False,
        convert_to: str | None = None,
    ) -> str:
        """Upload media from a public URL to the WordPress media library."""
        try:
            ssrf = ssrf_check(url)
            if not ssrf.allowed:
                raise UploadError(
                    "SSRF", ssrf.reason or "URL rejected by SSRF guard.", {"url": url}
                )

            data, declared_ct, fname_guess = await fetch_url_bytes(url, max_bytes=DEFAULT_MAX_BYTES)
            data, mime_hint = _maybe_optimize(
                data, declared_ct, skip=skip_optimize, convert_to=convert_to
            )

            media = await wp_raw_upload(
                self.client,
                data,
                filename=filename or fname_guess,
                mime_hint=mime_hint or declared_ct,
                # F.5a.8.5: forward metadata so the companion's single-
                # call route (when advertised) bundles upload + attach +
                # featured in one PHP request. ``_apply_metadata_and_attach``
                # below is a no-op in that case.
                attach_to_post=attach_to_post,
                set_featured=set_featured,
                title=title,
                alt_text=alt_text,
                caption=caption,
            )
            await _apply_metadata_and_attach(
                self.client,
                media,
                title=title,
                alt_text=alt_text,
                caption=caption,
                attach_to_post=attach_to_post,
                set_featured=set_featured,
            )

            log_media_upload(
                site=self.client.site_url,
                user_id=self.user_id,
                mime=media.get("mime_type") or mime_hint or declared_ct,
                size_bytes=len(data),
                source="url",
                media_id=media.get("id"),
            )
            return json.dumps(_format_upload_result(media, source=url), indent=2)
        except UploadError as e:
            return json.dumps(e.to_dict(), indent=2)
        except Exception as e:
            return json.dumps(
                {"error_code": "INTERNAL", "message": f"Upload from URL failed: {e}"}, indent=2
            )

    async def upload_media_from_base64(
        self,
        data: str,
        filename: str,
        mime: str | None = None,
        title: str | None = None,
        alt_text: str | None = None,
        caption: str | None = None,
        attach_to_post: int | None = None,
        set_featured: bool = False,
        skip_optimize: bool = False,
        convert_to: str | None = None,
    ) -> str:
        """Upload a base64-encoded file to the WordPress media library."""
        try:
            raw = _decode_base64(data)
            raw, mime_hint = _maybe_optimize(raw, mime, skip=skip_optimize, convert_to=convert_to)

            media = await wp_raw_upload(
                self.client,
                raw,
                filename=filename,
                mime_hint=mime_hint or mime,
                # F.5a.8.5: single-call path when companion advertises it.
                attach_to_post=attach_to_post,
                set_featured=set_featured,
                title=title,
                alt_text=alt_text,
                caption=caption,
            )
            await _apply_metadata_and_attach(
                self.client,
                media,
                title=title,
                alt_text=alt_text,
                caption=caption,
                attach_to_post=attach_to_post,
                set_featured=set_featured,
            )

            log_media_upload(
                site=self.client.site_url,
                user_id=self.user_id,
                mime=media.get("mime_type") or mime_hint or mime,
                size_bytes=len(raw),
                source="base64",
                media_id=media.get("id"),
            )
            return json.dumps(_format_upload_result(media, source="base64"), indent=2)
        except UploadError as e:
            return json.dumps(e.to_dict(), indent=2)
        except Exception as e:
            return json.dumps(
                {"error_code": "INTERNAL", "message": f"Base64 upload failed: {e}"}, indent=2
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
