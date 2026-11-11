"""Chunked media upload tools (F.5a.5).

Exposes four tools that wrap `core.upload_sessions.UploadSessionStore`:

- `upload_media_chunked_start(filename, total_bytes, mime?, sha256?)`
- `upload_media_chunked_chunk(session_id, index, data_b64)`
- `upload_media_chunked_finish(session_id, title?, alt_text?, caption?,
                                attach_to_post?, set_featured?, skip_optimize?)`
- `upload_media_chunked_abort(session_id)`

At `finish`, reuses the existing F.5a.1/.2 primitives: assembled bytes →
optional Pillow optimization → `wp_raw_upload` → metadata/attach/featured.
"""

from __future__ import annotations

import base64 as _b64
import binascii
import json
import os
from typing import Any

from core.media_audit import log_media_upload
from core.upload_sessions import (
    UploadSessionError,
    UploadSessionStore,
    get_upload_session_store,
    make_session_owner_id,
)
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._media_core import wp_raw_upload
from plugins.wordpress.handlers._media_security import UploadError
from plugins.wordpress.handlers.media import (
    _apply_metadata_and_attach,
    _format_upload_result,
    _maybe_optimize,
)

_RECOMMENDED_CHUNK_BYTES = 1024 * 1024


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for ToolGenerator."""
    return [
        {
            "name": "upload_media_chunked_start",
            "method_name": "upload_media_chunked_start",
            "description": (
                "Start a chunked upload session for a large media file. "
                "Returns a session_id for finish/status/abort. On per-user "
                "MCP endpoints it also returns a relative upload_url so an "
                "agent can PUT raw bytes with curl --data-binary @file, using "
                "the same Bearer token, instead of embedding large base64 in "
                "tool calls. Use the chunk tool only as the fallback path. TTL "
                "1h, hard cap 500 MB per session."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename with extension."},
                    "total_bytes": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Declared total size in bytes.",
                    },
                    "mime": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "MIME hint; still sniffed at finish.",
                    },
                    "sha256": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Optional hex sha256 of the full payload; verified at finish.",
                    },
                },
                "required": ["filename", "total_bytes"],
            },
            "scope": "write",
        },
        {
            "name": "upload_media_chunked_chunk",
            "method_name": "upload_media_chunked_chunk",
            "description": (
                "Append a single base64-encoded chunk to a chunked upload session. "
                "Chunks must arrive in order starting at index 0. Prefer the "
                "upload_url returned by upload_media_chunked_start when it is "
                "available; this base64 tool is the portable fallback."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "index": {"type": "integer", "minimum": 0},
                    "data_b64": {
                        "type": "string",
                        "description": "Base64-encoded chunk bytes.",
                    },
                    "chunk_sha256": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Optional hex sha256 of this chunk.",
                    },
                },
                "required": ["session_id", "index", "data_b64"],
            },
            "scope": "write",
        },
        {
            "name": "upload_media_chunked_finish",
            "method_name": "upload_media_chunked_finish",
            "description": (
                "Finalize a chunked upload: assemble + optimize + upload to "
                "WordPress. Verifies sha256 if supplied at start."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "title": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "alt_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "caption": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "attach_to_post": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                    },
                    "set_featured": {"type": "boolean", "default": False},
                    "skip_optimize": {"type": "boolean", "default": False},
                },
                "required": ["session_id"],
            },
            "scope": "write",
        },
        {
            "name": "upload_media_chunked_abort",
            "method_name": "upload_media_chunked_abort",
            "description": "Abort a chunked upload session and delete its spill file.",
            "schema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                },
                "required": ["session_id"],
            },
            "scope": "write",
        },
        {
            "name": "upload_media_chunked_status",
            "method_name": "upload_media_chunked_status",
            "description": (
                "Query the current state of a chunked-upload session — returns "
                "``received_bytes`` and ``next_chunk`` so the caller can resume "
                "after a disconnect. The session survives for 1 h after the "
                "last activity; re-start the session with ``upload_media_chunked_start`` "
                "if it has expired or been aborted. Returns ``{error_code: "
                "NOT_FOUND}`` when the session is unknown."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by upload_media_chunked_start.",
                    },
                },
                "required": ["session_id"],
            },
            "scope": "read",
        },
        {
            "name": "media_upload_workflow_status",
            "method_name": "media_upload_workflow_status",
            "description": (
                "Report WordPress media workflow capabilities for general "
                "agents. Shows whether AI image generation is enabled or "
                "disabled_missing_provider_key, and lists the recommended "
                "fallback path for public URLs, small attachments, and larger "
                "agent-local/chat-attached files."
            ),
            "schema": {
                "type": "object",
                "properties": {},
            },
            "scope": "read",
        },
    ]


def _decode_chunk(data_b64: str) -> bytes:
    s = (data_b64 or "").strip()
    if s.startswith("data:") and "," in s:
        s = s.split(",", 1)[1]
    s = s.replace("\n", "").replace("\r", "").replace(" ", "")
    try:
        return _b64.b64decode(s, validate=True)
    except (binascii.Error, ValueError) as e:
        raise UploadSessionError("BAD_BASE64", f"Invalid base64 chunk: {e}") from e


class MediaChunkedHandler:
    """Chunked-upload tool handler for the WordPress plugin."""

    def __init__(
        self,
        client: WordPressClient,
        *,
        user_id: str | None = None,
        site_id: str | None = None,
        alias: str | None = None,
        store: UploadSessionStore | None = None,
    ) -> None:
        self.client = client
        self.actor_user_id = user_id
        self.site_id = site_id
        self.alias = alias
        self.user_id = make_session_owner_id(user_id, site_id)
        self._store = store

    @property
    def store(self) -> UploadSessionStore:
        return self._store or get_upload_session_store()

    def _public_session_payload(self, sess) -> dict[str, Any]:
        payload = sess.to_public_dict()
        payload["max_bytes"] = self.store.max_session_bytes
        payload["recommended_chunk_bytes"] = _RECOMMENDED_CHUNK_BYTES
        payload["handoff"] = "stream_base64_chunks"
        if self.user_id == "admin":
            public_url = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
            upload_path = f"/admin/media-upload/{sess.id}"
            upload_url = f"{public_url}{upload_path}" if public_url else upload_path
            from core.media_intake import make_admin_browser_upload_url

            payload["handoff"] = "admin_http_binary_put"
            payload["upload"] = {
                "method": "PUT",
                "url": upload_url,
                "auth": "Use the same Authorization: Bearer *** as this MCP endpoint.",
                "content_type": "application/octet-stream",
                "curl": f"curl -X PUT -H 'Authorization: Bearer ***' --data-binary @FILE '{upload_url}'",
            }
            payload["browser_url"] = make_admin_browser_upload_url(sess.id)
            payload["fallback_handoff"] = "stream_base64_chunks"
        elif self.actor_user_id and self.alias:
            from core.media_intake import make_browser_upload_url

            public_url = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
            upload_path = f"/u/{self.actor_user_id}/{self.alias}/media-upload/{sess.id}"
            upload_url = f"{public_url}{upload_path}" if public_url else upload_path
            payload["handoff"] = "http_binary_put"
            payload["upload"] = {
                "method": "PUT",
                "url": upload_url,
                "auth": "Use the same Authorization: Bearer *** as this MCP endpoint.",
                "content_type": "application/octet-stream",
                "curl": f"curl -X PUT -H 'Authorization: Bearer ***' --data-binary @FILE '{upload_url}'",
            }
            payload["browser_url"] = make_browser_upload_url(
                sess.id,
                owner=self.actor_user_id,
                site_id=self.site_id,
                alias=self.alias,
                upload_path=upload_path,
            )
            payload["fallback_handoff"] = "stream_base64_chunks"
        return payload

    async def upload_media_chunked_start(
        self,
        filename: str,
        total_bytes: int,
        mime: str | None = None,
        sha256: str | None = None,
    ) -> str:
        try:
            sess = await self.store.start(
                user_id=self.user_id,
                filename=filename,
                total_bytes=total_bytes,
                mime=mime,
                sha256=sha256,
            )
            return json.dumps(self._public_session_payload(sess), indent=2)
        except UploadSessionError as e:
            return json.dumps(e.to_dict(), indent=2)

    async def upload_media_chunked_chunk(
        self,
        session_id: str,
        index: int,
        data_b64: str,
        chunk_sha256: str | None = None,
    ) -> str:
        try:
            data = _decode_chunk(data_b64)
            sess = await self.store.append_chunk(session_id, index, data, chunk_sha256=chunk_sha256)
            return json.dumps(self._public_session_payload(sess), indent=2)
        except UploadSessionError as e:
            return json.dumps(e.to_dict(), indent=2)

    async def upload_media_chunked_finish(
        self,
        session_id: str,
        title: str | None = None,
        alt_text: str | None = None,
        caption: str | None = None,
        attach_to_post: int | None = None,
        set_featured: bool = False,
        skip_optimize: bool = False,
    ) -> str:
        from core.tool_rate_limiter import ToolRateLimitError, get_tool_rate_limiter

        try:
            get_tool_rate_limiter().check(
                "wordpress_upload_media_chunked_finish",
                self.actor_user_id if self.actor_user_id else None,
            )
        except ToolRateLimitError as e:
            return json.dumps(e.to_dict(), indent=2)

        try:
            sess, assembled = await self.store.finalize(session_id)
            data, mime_hint = _maybe_optimize(assembled, sess.mime, skip=skip_optimize)
            media = await wp_raw_upload(
                self.client,
                data,
                filename=sess.filename,
                mime_hint=mime_hint or sess.mime,
                # F.5a.8.5: single-call upload+metadata+attach+featured
                # when the companion advertises it.
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
                user_id=self.actor_user_id,
                mime=media.get("mime_type") or mime_hint or sess.mime,
                size_bytes=len(data),
                source="chunked",
                media_id=media.get("id"),
            )
            return json.dumps(_format_upload_result(media, source="chunked"), indent=2)
        except UploadSessionError as e:
            return json.dumps(e.to_dict(), indent=2)
        except UploadError as e:
            return json.dumps(e.to_dict(), indent=2)
        except Exception as e:  # noqa: BLE001
            return json.dumps(
                {"error_code": "INTERNAL", "message": f"Chunked finish failed: {e}"}, indent=2
            )

    async def upload_media_chunked_status(self, session_id: str) -> str:
        """Return the current received_bytes / next_chunk for a session.

        Enables a resume-after-disconnect flow: the client keeps the
        session_id from the original ``start`` call, then queries this
        tool to discover how many bytes the server already has before
        resuming ``chunk`` calls at the reported ``next_chunk`` index.
        Aborted sessions (spill file gone) still return their last
        known status, clearly marked by the ``status`` field.
        """
        try:
            sess = await self.store.get(session_id)
            if sess is None:
                return json.dumps(
                    {
                        "error_code": "NO_SESSION",
                        "message": (
                            "Session not found. Either it has never existed, "
                            "already been finalised, or been aborted. Start a "
                            "new session with upload_media_chunked_start."
                        ),
                        "session_id": session_id,
                    },
                    indent=2,
                )
            return json.dumps(self._public_session_payload(sess), indent=2)
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "error_code": "INTERNAL",
                    "message": f"Status lookup failed: {exc}",
                    "session_id": session_id,
                },
                indent=2,
            )

    async def upload_media_chunked_abort(self, session_id: str) -> str:
        removed = await self.store.abort(session_id)
        return json.dumps({"session_id": session_id, "aborted": bool(removed)}, indent=2)

    async def media_upload_workflow_status(self) -> str:
        """Return a compact media workflow decision matrix for agents."""
        configured_providers: list[str] = []
        if self.site_id:
            try:
                from core.site_api import list_site_providers_set

                configured_providers = sorted(await list_site_providers_set(self.site_id))
            except Exception:
                configured_providers = []

        has_http_intake = bool(self.actor_user_id and self.alias)
        public_url = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
        payload = {
            "ai_image_generation": {
                "status": ("enabled" if configured_providers else "disabled_missing_provider_key"),
                "configured_providers": configured_providers,
                "tool": "wordpress_generate_and_upload_image",
                "note": (
                    "Use this only when a provider key is configured for the site. "
                    "Otherwise generate/use the image outside MCPHub and upload it "
                    "with one of the fallback paths below."
                ),
            },
            "fallbacks": [
                {
                    "when": "public_or_short_lived_https_url",
                    "tool": "wordpress_upload_media_from_url",
                },
                {
                    "when": "small_chat_attachment",
                    "tool": "wordpress_upload_media_from_base64",
                    "practical_limit": "about 10 MB in one tool call",
                },
                {
                    "when": "larger_chat_attachment_or_agent_local_file",
                    "start_tool": "wordpress_upload_media_chunked_start",
                    "preferred_handoff": (
                        "http_binary_put" if has_http_intake else "stream_base64_chunks"
                    ),
                    "finish_tool": "wordpress_upload_media_chunked_finish",
                    "status_tool": "wordpress_upload_media_chunked_status",
                },
            ],
            "media_intake": {
                "available": has_http_intake,
                "browser_upload": has_http_intake,
                "endpoint_template": (
                    f"{public_url}/u/{self.actor_user_id}/{self.alias}/media-upload/{{session_id}}"
                    if has_http_intake and public_url
                    else (
                        (
                            f"/u/{self.actor_user_id}/{self.alias}/media-upload/{{session_id}}"
                            if has_http_intake
                            else None
                        )
                        if has_http_intake
                        else None
                    )
                ),
                "auth": "same Bearer token as the MCP endpoint" if has_http_intake else None,
            },
        }
        return json.dumps(payload, indent=2)
