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
from typing import Any

from core.media_audit import log_media_upload
from core.upload_sessions import (
    UploadSessionError,
    UploadSessionStore,
    get_upload_session_store,
)
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._media_core import wp_raw_upload
from plugins.wordpress.handlers._media_security import UploadError
from plugins.wordpress.handlers.media import (
    _apply_metadata_and_attach,
    _format_upload_result,
    _maybe_optimize,
)


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for ToolGenerator."""
    return [
        {
            "name": "upload_media_chunked_start",
            "method_name": "upload_media_chunked_start",
            "description": (
                "Start a chunked upload session for a large media file. "
                "Returns a session_id to use for subsequent chunk/finish/abort "
                "calls. TTL 1h, hard cap 500 MB per session."
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
                "Chunks must arrive in order starting at index 0."
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
        store: UploadSessionStore | None = None,
    ) -> None:
        self.client = client
        self.user_id = user_id or "admin"
        self._store = store

    @property
    def store(self) -> UploadSessionStore:
        return self._store or get_upload_session_store()

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
            return json.dumps(sess.to_public_dict(), indent=2)
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
            return json.dumps(sess.to_public_dict(), indent=2)
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
                self.user_id if self.user_id != "admin" else None,
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
                user_id=self.user_id if self.user_id != "admin" else None,
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
            return json.dumps(sess.to_public_dict(), indent=2)
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
