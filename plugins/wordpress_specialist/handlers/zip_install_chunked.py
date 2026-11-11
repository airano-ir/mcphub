"""Chunked staging tools for WordPress plugin/theme install zips.

These tools bridge the common agent/operator-elsewhere case: the zip is
local to Claude Code, code-server, or another agent workspace, while MCPHub
runs on a different filesystem. The agent streams chunks to MCPHub, then
passes the returned ``zip_session_id`` to the existing plugin/theme install
tools.
"""

from __future__ import annotations

import base64 as _b64
import binascii
import json
import os
from typing import Any

from core.upload_sessions import (
    UploadSessionError,
    UploadSessionStore,
    get_upload_session_store,
    make_session_owner_id,
)
from plugins.wordpress_specialist.handlers._zip_payload import ZIP_INSTALL_SESSION_MIME

_ZIP_INSTALL_MAX_BYTES = 50 * 1024 * 1024
_RECOMMENDED_CHUNK_BYTES = 1024 * 1024


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for WordPress install zip staging."""
    return [
        {
            "name": "wp_zip_install_chunked_start",
            "method_name": "wp_zip_install_chunked_start",
            "description": (
                "Start a chunked staging session for a WordPress plugin or theme "
                "zip. Use the returned session_id as zip_session_id in "
                "wp_plugin_install_from_zip or wp_theme_install_from_zip. On "
                "per-user MCP endpoints this also returns a relative upload_url "
                "so an agent can PUT raw zip bytes with curl --data-binary "
                "@file, using the same Bearer token, instead of embedding large "
                "base64 in tool calls. Use the chunk tool only as the fallback "
                "path. TTL 1h, hard cap 50 MB per zip."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Zip filename only, for example premium-plugin.zip.",
                    },
                    "total_bytes": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _ZIP_INSTALL_MAX_BYTES,
                        "description": "Declared zip size in bytes.",
                    },
                    "sha256": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": (
                            "Optional hex sha256 of the full zip payload; verified "
                            "when the install tool finalizes the session."
                        ),
                    },
                },
                "required": ["filename", "total_bytes"],
            },
            "scope": "admin",
        },
        {
            "name": "wp_zip_install_chunked_chunk",
            "method_name": "wp_zip_install_chunked_chunk",
            "description": (
                "Append one base64-encoded chunk to a WordPress install zip "
                "staging session. Chunks must arrive in order starting at index "
                "0. Prefer the upload_url returned by wp_zip_install_chunked_start "
                "when it is available; this base64 tool is the portable fallback."
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
            "scope": "admin",
        },
        {
            "name": "wp_zip_install_chunked_status",
            "method_name": "wp_zip_install_chunked_status",
            "description": (
                "Query a WordPress install zip staging session. Returns "
                "received_bytes and next_chunk so the caller can resume after a "
                "disconnect."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by wp_zip_install_chunked_start.",
                    },
                },
                "required": ["session_id"],
            },
            "scope": "admin",
        },
        {
            "name": "wp_zip_install_chunked_abort",
            "method_name": "wp_zip_install_chunked_abort",
            "description": "Abort a WordPress install zip staging session and delete its spill file.",
            "schema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                },
                "required": ["session_id"],
            },
            "scope": "admin",
        },
    ]


def _validate_start_args(filename: Any, total_bytes: Any) -> tuple[str, int]:
    if not isinstance(filename, str):
        raise UploadSessionError("BAD_FILENAME", "filename must be a string.")
    clean = filename.strip()
    if not clean:
        raise UploadSessionError("BAD_FILENAME", "filename must be non-empty.")
    if "/" in clean or "\\" in clean:
        raise UploadSessionError("BAD_FILENAME", "filename must not contain path separators.")
    if not clean.lower().endswith(".zip"):
        raise UploadSessionError("BAD_FILENAME", "filename must end with .zip.")
    if isinstance(total_bytes, bool) or not isinstance(total_bytes, int):
        raise UploadSessionError("BAD_SIZE", "total_bytes must be an integer.")
    if total_bytes <= 0:
        raise UploadSessionError("BAD_SIZE", "total_bytes must be positive.")
    if total_bytes > _ZIP_INSTALL_MAX_BYTES:
        raise UploadSessionError(
            "SESSION_TOO_LARGE",
            f"total_bytes {total_bytes} exceeds limit {_ZIP_INSTALL_MAX_BYTES}.",
            {"max": _ZIP_INSTALL_MAX_BYTES},
        )
    return clean, total_bytes


def _decode_chunk(data_b64: str) -> bytes:
    s = (data_b64 or "").strip()
    if s.startswith("data:") and "," in s:
        s = s.split(",", 1)[1]
    s = s.replace("\n", "").replace("\r", "").replace(" ", "")
    try:
        return _b64.b64decode(s, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise UploadSessionError("BAD_BASE64", f"Invalid base64 chunk: {exc}") from exc


class ZipInstallChunkedHandler:
    """Chunked staging handler for WordPress install zips."""

    def __init__(
        self,
        *,
        user_id: str | None = None,
        site_id: str | None = None,
        alias: str | None = None,
        store: UploadSessionStore | None = None,
    ) -> None:
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
        payload["max_bytes"] = _ZIP_INSTALL_MAX_BYTES
        payload["recommended_chunk_bytes"] = _RECOMMENDED_CHUNK_BYTES
        payload["handoff"] = "stream_base64_chunks"
        if self.actor_user_id and self.actor_user_id != "admin" and self.alias:
            public_url = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
            upload_path = f"/u/{self.actor_user_id}/{self.alias}/zip-install-upload/{sess.id}"
            upload_url = f"{public_url}{upload_path}" if public_url else upload_path
            payload["handoff"] = "http_binary_put"
            payload["upload"] = {
                "method": "PUT",
                "url": upload_url,
                "auth": "Use the same Authorization: Bearer token as this MCP endpoint.",
                "content_type": "application/zip",
                "curl": (
                    "curl -X PUT -H 'Authorization: Bearer $MCPHUB_TOKEN' "
                    f"--data-binary @FILE '{upload_url}'"
                ),
            }
            payload["fallback_handoff"] = "stream_base64_chunks"
        return payload

    async def wp_zip_install_chunked_start(
        self,
        filename: str,
        total_bytes: int,
        sha256: str | None = None,
    ) -> str:
        try:
            clean_filename, clean_total = _validate_start_args(filename, total_bytes)
            sess = await self.store.start(
                user_id=self.user_id,
                filename=clean_filename,
                total_bytes=clean_total,
                mime=ZIP_INSTALL_SESSION_MIME,
                sha256=sha256,
            )
            return json.dumps(self._public_session_payload(sess), indent=2)
        except UploadSessionError as exc:
            return json.dumps(exc.to_dict(), indent=2)

    async def wp_zip_install_chunked_chunk(
        self,
        session_id: str,
        index: int,
        data_b64: str,
        chunk_sha256: str | None = None,
    ) -> str:
        try:
            data = _decode_chunk(data_b64)
            sess = await self.store.append_chunk(
                session_id,
                index,
                data,
                chunk_sha256=chunk_sha256,
            )
            return json.dumps(self._public_session_payload(sess), indent=2)
        except UploadSessionError as exc:
            return json.dumps(exc.to_dict(), indent=2)

    async def wp_zip_install_chunked_status(self, session_id: str) -> str:
        try:
            sess = await self.store.get(session_id)
            if sess is None:
                return json.dumps(
                    {
                        "error_code": "NO_SESSION",
                        "message": (
                            "Session not found. It may have never existed, already "
                            "been finalized by an install tool, or been aborted."
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

    async def wp_zip_install_chunked_abort(self, session_id: str) -> str:
        removed = await self.store.abort(session_id)
        return json.dumps({"session_id": session_id, "aborted": bool(removed)}, indent=2)
