"""Helpers for WordPress Specialist zip-install payloads."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path
from typing import Any

from core.upload_sessions import (
    UploadSessionError,
    UploadSessionStore,
    get_upload_session_store,
)
from core.zip_install_sessions import ZIP_INSTALL_SESSION_MIME


def zip_bytes_to_base64(data: bytes, *, max_bytes: int, source_label: str) -> str:
    """Validate assembled zip bytes and return a base64 body."""
    if len(data) > max_bytes:
        raise ValueError(
            f"{source_label} is {len(data)} bytes -- exceeds {max_bytes} byte cap (S-18)"
        )
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError(f"{source_label} must be a valid zip archive")
    return base64.b64encode(data).decode("ascii")


async def zip_session_to_base64(
    zip_session_id: Any,
    *,
    max_bytes: int,
    store: UploadSessionStore | None = None,
) -> str:
    """Finalize a staged install zip session and return its base64 body."""
    if not isinstance(zip_session_id, str):
        raise ValueError("zip_session_id must be a string")

    session_id = zip_session_id.strip()
    if not session_id:
        raise ValueError("zip_session_id must be a non-empty string")

    upload_store = store or get_upload_session_store()
    sess = await upload_store.get(session_id)
    if sess is None:
        raise UploadSessionError(
            "NO_SESSION",
            f"Session {session_id} not found.",
            {"session_id": session_id},
        )
    if sess.mime != ZIP_INSTALL_SESSION_MIME:
        raise ValueError("zip_session_id must reference a WordPress install zip session")
    if sess.total_bytes > max_bytes:
        raise ValueError(
            f"zip_session_id payload is {sess.total_bytes} bytes -- exceeds "
            f"{max_bytes} byte cap (S-18)"
        )

    _, data = await upload_store.finalize(session_id)
    return zip_bytes_to_base64(data, max_bytes=max_bytes, source_label="zip_session_id payload")


def local_zip_to_base64(zip_path: Any, *, max_bytes: int) -> str:
    """Read a server-local zip file and return its base64 body.

    This avoids passing multi-megabyte base64 strings through the LLM/tool
    call context. The companion route still receives its existing
    ``zip_base64`` contract, so no PHP plugin change is needed.
    """
    if not isinstance(zip_path, str):
        raise ValueError("zip_path must be a string")

    raw_path = zip_path.strip()
    if not raw_path:
        raise ValueError("zip_path must be a non-empty string")

    path = Path(raw_path).expanduser()
    try:
        stat = path.lstat()
    except OSError as exc:
        raise ValueError(f"zip_path is not readable: {raw_path}") from exc

    if path.is_symlink():
        raise ValueError("zip_path must not be a symlink")
    if not path.is_file():
        raise ValueError("zip_path must point to a regular file")
    if path.suffix.lower() != ".zip":
        raise ValueError("zip_path must point to a .zip file")
    if stat.st_size > max_bytes:
        raise ValueError(
            f"zip_path file is {stat.st_size} bytes -- exceeds {max_bytes} byte cap (S-18)"
        )
    if not zipfile.is_zipfile(path):
        raise ValueError("zip_path must point to a valid zip archive")

    data = path.read_bytes()
    return zip_bytes_to_base64(data, max_bytes=max_bytes, source_label="zip_path file")
