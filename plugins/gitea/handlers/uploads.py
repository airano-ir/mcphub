"""Gitea release asset binary upload tools."""

from __future__ import annotations

import base64 as _b64
import binascii
import json
import os
import re
from datetime import UTC, datetime
from typing import Any

from core.gitea_upload_sessions import (
    GiteaUploadMetadata,
    delete_gitea_upload_metadata,
    get_gitea_upload_metadata,
    is_gitea_upload_mime,
    make_gitea_upload_mime,
    upsert_gitea_upload_metadata,
)
from core.upload_sessions import (
    UploadSession,
    UploadSessionError,
    UploadSessionStore,
    get_upload_session_store,
    make_session_owner_id,
)
from plugins.gitea.client import GiteaClient

_GITEA_UPLOAD_MAX_BYTES = int(
    os.environ.get("MCPHUB_GITEA_UPLOAD_MAX_BYTES", str(500 * 1024 * 1024))
)
_RECOMMENDED_CHUNK_BYTES = 1024 * 1024
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "upload_release_asset",
            "method_name": "upload_release_asset",
            "description": (
                "Upload a small base64-encoded release asset to a Gitea release. "
                "For larger files, prefer gitea_upload_start plus the returned "
                "HTTP upload URL, then gitea_upload_finish."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "minLength": 1},
                    "repo": {"type": "string", "minLength": 1},
                    "release_id": {"type": "integer", "minimum": 1},
                    "filename": {"type": "string", "minLength": 1},
                    "content_b64": {
                        "type": "string",
                        "description": "Base64 asset bytes. Use only for small payloads.",
                    },
                },
                "required": ["owner", "repo", "release_id", "filename", "content_b64"],
            },
            "scope": "write",
        },
        {
            "name": "upload_start",
            "method_name": "upload_start",
            "description": (
                "Start a Gitea binary upload session. First supported kind is "
                "release_asset. On per-user MCP endpoints this returns "
                "/u/{user_id}/{alias}/gitea-upload/{session_id}, so callers can "
                "PUT raw bytes with curl --data-binary @file using the same "
                "Bearer token. TTL 1h, hard cap 500 MB by default."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["release_asset"],
                        "default": "release_asset",
                    },
                    "owner": {"type": "string", "minLength": 1},
                    "repo": {"type": "string", "minLength": 1},
                    "release_id": {"type": "integer", "minimum": 1},
                    "filename": {"type": "string", "minLength": 1},
                    "total_bytes": {"type": "integer", "minimum": 1},
                    "sha256": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Optional full-payload sha256, verified at finish.",
                    },
                },
                "required": ["owner", "repo", "release_id", "filename", "total_bytes"],
            },
            "scope": "write",
        },
        {
            "name": "upload_chunk",
            "method_name": "upload_chunk",
            "description": (
                "Append one base64-encoded chunk to a Gitea binary upload session. "
                "Chunks must arrive in order. Prefer the HTTP upload URL from "
                "gitea_upload_start when available; this is the fallback path."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "index": {"type": "integer", "minimum": 0},
                    "data_b64": {"type": "string"},
                    "chunk_sha256": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
                "required": ["session_id", "index", "data_b64"],
            },
            "scope": "write",
        },
        {
            "name": "upload_status",
            "method_name": "upload_status",
            "description": "Query a Gitea binary upload session status and target metadata.",
            "schema": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
            "scope": "read",
        },
        {
            "name": "upload_abort",
            "method_name": "upload_abort",
            "description": "Abort a Gitea binary upload session and delete its spill file.",
            "schema": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
            "scope": "write",
        },
        {
            "name": "upload_finish",
            "method_name": "upload_finish",
            "description": (
                "Finalize a complete Gitea binary upload session. For "
                "release_asset sessions this verifies optional sha256, then sends "
                "the original bytes to Gitea as multipart/form-data."
            ),
            "schema": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
            "scope": "write",
        },
    ]


def _clean_segment(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise UploadSessionError(f"BAD_{label.upper()}", f"{label} must be a string.")
    clean = value.strip()
    if not clean or clean in {".", ".."}:
        raise UploadSessionError(f"BAD_{label.upper()}", f"{label} must be non-empty.")
    if "/" in clean or "\\" in clean or any(ord(ch) < 32 for ch in clean):
        raise UploadSessionError(
            f"BAD_{label.upper()}",
            f"{label} must not contain path separators or control characters.",
        )
    if not _SEGMENT_RE.match(clean):
        raise UploadSessionError(
            f"BAD_{label.upper()}",
            f"{label} contains unsupported characters.",
        )
    return clean


def _clean_filename(value: Any) -> str:
    if not isinstance(value, str):
        raise UploadSessionError("BAD_FILENAME", "filename must be a string.")
    clean = value.strip()
    if not clean or clean in {".", ".."}:
        raise UploadSessionError("BAD_FILENAME", "filename must be non-empty.")
    if len(clean.encode("utf-8")) > 255:
        raise UploadSessionError("BAD_FILENAME", "filename is too long.")
    if "/" in clean or "\\" in clean or any(ord(ch) < 32 for ch in clean):
        raise UploadSessionError(
            "BAD_FILENAME",
            "filename must not contain path separators or control characters.",
        )
    return clean


def _clean_total_bytes(value: Any, max_bytes: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UploadSessionError("BAD_SIZE", "total_bytes must be an integer.")
    if value <= 0:
        raise UploadSessionError("BAD_SIZE", "total_bytes must be positive.")
    if value > max_bytes:
        raise UploadSessionError(
            "SESSION_TOO_LARGE",
            f"total_bytes {value} exceeds limit {max_bytes}.",
            {"max": max_bytes},
        )
    return value


def _clean_release_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise UploadSessionError("BAD_RELEASE_ID", "release_id must be a positive integer.")
    return value


def _clean_sha256(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256_RE.match(value.strip()):
        raise UploadSessionError("BAD_SHA256", "sha256 must be a 64-character hex string.")
    return value.strip().lower()


def _decode_chunk(data_b64: str) -> bytes:
    s = (data_b64 or "").strip()
    if s.startswith("data:") and "," in s:
        s = s.split(",", 1)[1]
    s = s.replace("\n", "").replace("\r", "").replace(" ", "")
    try:
        return _b64.b64decode(s, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise UploadSessionError("BAD_BASE64", f"Invalid base64 chunk: {exc}") from exc


class GiteaUploadHandler:
    def __init__(
        self,
        client: GiteaClient,
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

    def _max_bytes(self) -> int:
        return min(_GITEA_UPLOAD_MAX_BYTES, self.store.max_session_bytes)

    def _public_session_payload(
        self,
        sess: UploadSession,
        meta: GiteaUploadMetadata,
    ) -> dict[str, Any]:
        payload = sess.to_public_dict()
        payload.update(meta.to_public_dict())
        payload["max_bytes"] = self._max_bytes()
        payload["recommended_chunk_bytes"] = _RECOMMENDED_CHUNK_BYTES
        payload["handoff"] = "stream_base64_chunks"
        payload["finish_tool"] = "gitea_upload_finish"
        if self.actor_user_id and self.actor_user_id != "admin" and self.alias:
            public_url = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
            upload_path = f"/u/{self.actor_user_id}/{self.alias}/gitea-upload/{sess.id}"
            upload_url = f"{public_url}{upload_path}" if public_url else upload_path
            payload["handoff"] = "http_binary_put"
            payload["upload"] = {
                "method": "PUT",
                "url": upload_url,
                "auth": "Use the same Authorization: Bearer token as this MCP endpoint.",
                "content_type": "application/octet-stream",
                "curl": (
                    "curl -X PUT -H 'Authorization: Bearer $MCPHUB_TOKEN' "
                    f"--data-binary @FILE '{upload_url}'"
                ),
            }
            payload["fallback_handoff"] = "stream_base64_chunks"
        return payload

    async def _require_owned_session(
        self,
        session_id: str,
    ) -> tuple[UploadSession, GiteaUploadMetadata]:
        sess = await self.store.get(session_id)
        if sess is None:
            raise UploadSessionError("NO_SESSION", f"Session {session_id} not found.")
        if not is_gitea_upload_mime(sess.mime):
            raise UploadSessionError(
                "BAD_SESSION_TYPE",
                "Session is not a Gitea binary upload session.",
            )
        meta = await get_gitea_upload_metadata(self.store.db, session_id)
        if meta is None:
            raise UploadSessionError(
                "BAD_SESSION_TYPE",
                "Gitea upload metadata is missing for this session.",
            )
        if sess.user_id != self.user_id:
            raise UploadSessionError(
                "FORBIDDEN",
                "Upload session does not belong to this user/site.",
            )
        if self.site_id and meta.site_id != self.site_id:
            raise UploadSessionError(
                "FORBIDDEN",
                "Upload session is scoped to a different site.",
            )
        if meta.plugin_type != "gitea":
            raise UploadSessionError("BAD_SESSION_TYPE", "Session is not scoped to Gitea.")
        return sess, meta

    async def upload_release_asset(
        self,
        owner: str,
        repo: str,
        release_id: int,
        filename: str,
        content_b64: str,
    ) -> str:
        try:
            clean_owner = _clean_segment(owner, "owner")
            clean_repo = _clean_segment(repo, "repo")
            clean_release_id = _clean_release_id(release_id)
            clean_filename = _clean_filename(filename)
            asset = await self.client.upload_release_asset(
                clean_owner,
                clean_repo,
                clean_release_id,
                filename=clean_filename,
                content_b64=content_b64,
            )
            return json.dumps({"success": True, "asset": asset}, indent=2)
        except (UploadSessionError, ValueError) as exc:
            if isinstance(exc, UploadSessionError):
                return json.dumps(exc.to_dict(), indent=2)
            return json.dumps({"error_code": "BAD_BASE64", "message": str(exc)}, indent=2)
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {"error_code": "GITEA_UPLOAD_FAILED", "message": str(exc)},
                indent=2,
            )

    async def upload_start(
        self,
        owner: str,
        repo: str,
        release_id: int,
        filename: str,
        total_bytes: int,
        kind: str = "release_asset",
        sha256: str | None = None,
    ) -> str:
        try:
            clean_kind = (kind or "release_asset").strip()
            if clean_kind != "release_asset":
                raise UploadSessionError(
                    "BAD_KIND",
                    "Only kind='release_asset' is supported for Gitea uploads.",
                )
            target = {
                "owner": _clean_segment(owner, "owner"),
                "repo": _clean_segment(repo, "repo"),
                "release_id": _clean_release_id(release_id),
                "filename": _clean_filename(filename),
            }
            clean_total = _clean_total_bytes(total_bytes, self._max_bytes())
            clean_sha = _clean_sha256(sha256)
            sess = await self.store.start(
                user_id=self.user_id,
                filename=target["filename"],
                total_bytes=clean_total,
                mime=make_gitea_upload_mime(clean_kind, target),
                sha256=clean_sha,
            )
            meta = await upsert_gitea_upload_metadata(
                self.store.db,
                session_id=sess.id,
                owner_user_id=self.actor_user_id or "admin",
                site_id=self.site_id or "admin",
                alias=self.alias or "admin",
                kind=clean_kind,
                target=target,
            )
            return json.dumps(self._public_session_payload(sess, meta), indent=2)
        except UploadSessionError as exc:
            return json.dumps(exc.to_dict(), indent=2)

    async def upload_chunk(
        self,
        session_id: str,
        index: int,
        data_b64: str,
        chunk_sha256: str | None = None,
    ) -> str:
        try:
            await self._require_owned_session(session_id)
            data = _decode_chunk(data_b64)
            sess = await self.store.append_chunk(
                session_id,
                index,
                data,
                chunk_sha256=chunk_sha256,
            )
            meta = await get_gitea_upload_metadata(self.store.db, session_id)
            assert meta is not None
            return json.dumps(self._public_session_payload(sess, meta), indent=2)
        except UploadSessionError as exc:
            return json.dumps(exc.to_dict(), indent=2)

    async def upload_status(self, session_id: str) -> str:
        try:
            sess, meta = await self._require_owned_session(session_id)
            payload = self._public_session_payload(sess, meta)
            payload["expired"] = sess.expires_at <= datetime.now(UTC)
            if payload["expired"]:
                payload["error_code"] = "EXPIRED"
                payload["message"] = f"Session {session_id} has expired."
            return json.dumps(payload, indent=2)
        except UploadSessionError as exc:
            return json.dumps(exc.to_dict(), indent=2)
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "error_code": "INTERNAL",
                    "message": f"Status lookup failed: {exc}",
                    "session_id": session_id,
                },
                indent=2,
            )

    async def upload_abort(self, session_id: str) -> str:
        try:
            await self._require_owned_session(session_id)
            removed = await self.store.abort(session_id)
            if not removed:
                await delete_gitea_upload_metadata(self.store.db, session_id)
            return json.dumps({"session_id": session_id, "aborted": bool(removed)}, indent=2)
        except UploadSessionError as exc:
            return json.dumps(exc.to_dict(), indent=2)

    async def upload_finish(self, session_id: str) -> str:
        try:
            _, meta = await self._require_owned_session(session_id)
            sess, assembled = await self.store.finalize(session_id)
            if meta.kind != "release_asset":
                raise UploadSessionError("BAD_KIND", f"Unsupported Gitea upload kind {meta.kind}.")
            target = meta.target
            asset = await self.client.upload_release_asset_bytes(
                target["owner"],
                target["repo"],
                int(target["release_id"]),
                filename=target["filename"],
                content=assembled,
            )
            return json.dumps(
                {
                    "success": True,
                    "kind": meta.kind,
                    "session_id": sess.id,
                    "filename": target["filename"],
                    "bytes_uploaded": len(assembled),
                    "asset": asset,
                },
                indent=2,
            )
        except UploadSessionError as exc:
            return json.dumps(exc.to_dict(), indent=2)
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {"error_code": "GITEA_UPLOAD_FAILED", "message": str(exc)},
                indent=2,
            )
