"""Chunked upload session store (F.5a.5).

Server-side buffering for large media uploads: SQLite metadata + disk spill.
Sessions are deterministic (same user+file metadata yields the same
session_id), enabling resumable uploads. Enforces per-user concurrency
quota, per-session byte cap, and a 1h TTL reaped by a background task.

Chunks are appended sequentially; out-of-order or duplicate indexes raise
a typed error. Optional full-payload sha256 (supplied at `start`) is
verified when the session is finalized.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.database import Database, get_database

logger = logging.getLogger(__name__)


# --- Config ----------------------------------------------------------------

DEFAULT_SPILL_DIR = Path(os.environ.get("MCPHUB_UPLOAD_SPILL_DIR", "/tmp/mcphub-uploads"))
SESSION_TTL = timedelta(seconds=int(os.environ.get("MCPHUB_UPLOAD_TTL_SEC", "3600")))
MAX_SESSION_BYTES = int(os.environ.get("MCPHUB_UPLOAD_MAX_BYTES", str(500 * 1024 * 1024)))
MAX_CONCURRENT_PER_USER = int(os.environ.get("MCPHUB_UPLOAD_MAX_CONCURRENT", "10"))


# --- Errors ----------------------------------------------------------------


class UploadSessionError(Exception):
    """Typed session error with stable JSON code."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error_code": self.code, "message": self.message, "details": self.details}


# --- Helpers ---------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def make_session_id(
    user_id: str,
    filename: str,
    total_bytes: int,
    mime: str | None,
    sha256: str | None,
) -> str:
    """Deterministic session id — same tuple → same id (enables resume)."""
    payload = f"{user_id}|{filename}|{total_bytes}|{mime or ''}|{sha256 or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _ensure_spill_dir(spill_dir: Path) -> None:
    spill_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(spill_dir, 0o700)
    except OSError:
        pass


# --- Store -----------------------------------------------------------------


class UploadSession:
    """Runtime view of an upload session row."""

    __slots__ = (
        "id",
        "user_id",
        "filename",
        "total_bytes",
        "mime",
        "sha256",
        "received_bytes",
        "next_chunk",
        "spill_path",
        "status",
        "created_at",
        "expires_at",
    )

    def __init__(self, **kwargs: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, kwargs.get(name))

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> UploadSession:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            filename=row["filename"],
            total_bytes=int(row["total_bytes"]),
            mime=row["mime"],
            sha256=row["sha256"],
            received_bytes=int(row["received_bytes"]),
            next_chunk=int(row["next_chunk"]),
            spill_path=Path(row["spill_path"]),
            status=row["status"],
            created_at=_parse_iso(row["created_at"]),
            expires_at=_parse_iso(row["expires_at"]),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.id,
            "filename": self.filename,
            "total_bytes": self.total_bytes,
            "received_bytes": self.received_bytes,
            "next_chunk": self.next_chunk,
            "status": self.status,
            "expires_at": _iso(self.expires_at),
        }


class UploadSessionStore:
    """Persistent chunk-upload session store with disk spill."""

    def __init__(
        self,
        *,
        db: Database | None = None,
        spill_dir: Path | None = None,
        ttl: timedelta = SESSION_TTL,
        max_session_bytes: int = MAX_SESSION_BYTES,
        max_concurrent_per_user: int = MAX_CONCURRENT_PER_USER,
    ) -> None:
        self._db = db
        self.spill_dir = Path(spill_dir or DEFAULT_SPILL_DIR)
        self.ttl = ttl
        self.max_session_bytes = max_session_bytes
        self.max_concurrent_per_user = max_concurrent_per_user
        self._lock = asyncio.Lock()
        _ensure_spill_dir(self.spill_dir)

    @property
    def db(self) -> Database:
        return self._db or get_database()

    # -- start -------------------------------------------------------------

    async def start(
        self,
        *,
        user_id: str,
        filename: str,
        total_bytes: int,
        mime: str | None = None,
        sha256: str | None = None,
    ) -> UploadSession:
        if total_bytes <= 0:
            raise UploadSessionError("BAD_SIZE", "total_bytes must be positive.")
        if total_bytes > self.max_session_bytes:
            raise UploadSessionError(
                "SESSION_TOO_LARGE",
                f"total_bytes {total_bytes} exceeds limit {self.max_session_bytes}.",
                {"max": self.max_session_bytes},
            )

        session_id = make_session_id(user_id, filename, total_bytes, mime, sha256)

        async with self._lock:
            existing = await self._get_row(session_id)
            if existing is not None:
                sess = UploadSession.from_row(existing)
                if sess.status == "open" and sess.expires_at > _utc_now():
                    return sess
                # Stale/finished — replace
                await self._delete_row(session_id)
                _unlink_silent(sess.spill_path)

            open_count = await self._count_open_for_user(user_id)
            if open_count >= self.max_concurrent_per_user:
                raise UploadSessionError(
                    "QUOTA_EXCEEDED",
                    f"User has {open_count} open upload sessions "
                    f"(max {self.max_concurrent_per_user}).",
                    {"open": open_count, "max": self.max_concurrent_per_user},
                )

            now = _utc_now()
            expires = now + self.ttl
            spill_path = self.spill_dir / f"{session_id}.part"
            # Touch an empty spill file with 0600 perms
            _ensure_spill_dir(self.spill_dir)
            with open(spill_path, "wb") as f:
                f.truncate(0)
            try:
                os.chmod(spill_path, 0o600)
            except OSError:
                pass

            await self.db.execute(
                "INSERT INTO upload_sessions "
                "(id, user_id, filename, total_bytes, mime, sha256, "
                " received_bytes, next_chunk, spill_path, status, "
                " created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, 'open', ?, ?)",
                (
                    session_id,
                    user_id,
                    filename,
                    total_bytes,
                    mime,
                    sha256,
                    str(spill_path),
                    _iso(now),
                    _iso(expires),
                ),
            )
            return UploadSession(
                id=session_id,
                user_id=user_id,
                filename=filename,
                total_bytes=total_bytes,
                mime=mime,
                sha256=sha256,
                received_bytes=0,
                next_chunk=0,
                spill_path=spill_path,
                status="open",
                created_at=now,
                expires_at=expires,
            )

    # -- append chunk ------------------------------------------------------

    async def append_chunk(
        self,
        session_id: str,
        index: int,
        data: bytes,
        *,
        chunk_sha256: str | None = None,
    ) -> UploadSession:
        async with self._lock:
            sess = await self._require_open(session_id)
            if index != sess.next_chunk:
                raise UploadSessionError(
                    "CHUNK_ORDER",
                    f"Expected chunk index {sess.next_chunk}, got {index}.",
                    {"expected": sess.next_chunk, "got": index},
                )
            new_size = sess.received_bytes + len(data)
            if new_size > sess.total_bytes:
                raise UploadSessionError(
                    "CHUNK_OVERFLOW",
                    f"Chunk would exceed declared total_bytes "
                    f"({new_size} > {sess.total_bytes}).",
                    {"declared": sess.total_bytes, "would_be": new_size},
                )
            if chunk_sha256 is not None:
                actual = hashlib.sha256(data).hexdigest()
                if actual.lower() != chunk_sha256.lower():
                    raise UploadSessionError(
                        "CHUNK_CHECKSUM",
                        "Chunk sha256 does not match supplied value.",
                        {"expected": chunk_sha256, "actual": actual, "index": index},
                    )

            with open(sess.spill_path, "ab") as f:
                f.write(data)
            sess.received_bytes = new_size
            sess.next_chunk = index + 1
            await self.db.execute(
                "UPDATE upload_sessions SET received_bytes = ?, next_chunk = ? WHERE id = ?",
                (sess.received_bytes, sess.next_chunk, session_id),
            )
            return sess

    # -- finalize ----------------------------------------------------------

    async def finalize(self, session_id: str) -> tuple[UploadSession, bytes]:
        """Read the full spill file and verify. Returns (session, bytes).

        On checksum mismatch the session is kept (status remains 'open') so
        the caller can retry; on success, the row and spill file are removed.
        """
        async with self._lock:
            sess = await self._require_open(session_id)
            if sess.received_bytes != sess.total_bytes:
                raise UploadSessionError(
                    "INCOMPLETE",
                    f"Received {sess.received_bytes}/{sess.total_bytes} bytes.",
                    {
                        "received": sess.received_bytes,
                        "total": sess.total_bytes,
                    },
                )
            with open(sess.spill_path, "rb") as f:
                data = f.read()
            if sess.sha256:
                actual = hashlib.sha256(data).hexdigest()
                if actual.lower() != sess.sha256.lower():
                    raise UploadSessionError(
                        "CHECKSUM_MISMATCH",
                        "Assembled sha256 does not match value supplied at start.",
                        {"expected": sess.sha256, "actual": actual},
                    )
            # Success — drop the session
            await self._delete_row(session_id)
            _unlink_silent(sess.spill_path)
            return sess, data

    # -- abort -------------------------------------------------------------

    async def abort(self, session_id: str) -> bool:
        async with self._lock:
            row = await self._get_row(session_id)
            if row is None:
                return False
            sess = UploadSession.from_row(row)
            await self._delete_row(session_id)
            _unlink_silent(sess.spill_path)
            return True

    # -- get ---------------------------------------------------------------

    async def get(self, session_id: str) -> UploadSession | None:
        row = await self._get_row(session_id)
        return UploadSession.from_row(row) if row else None

    # -- cleanup -----------------------------------------------------------

    async def cleanup_expired(self, *, now: datetime | None = None) -> int:
        now = now or _utc_now()
        rows = await self.db.fetchall(
            "SELECT * FROM upload_sessions WHERE expires_at < ?", (_iso(now),)
        )
        reaped = 0
        for row in rows:
            sess = UploadSession.from_row(row)
            _unlink_silent(sess.spill_path)
            await self._delete_row(sess.id)
            reaped += 1
        if reaped:
            logger.info("Reaped %d expired upload session(s)", reaped)
        return reaped

    # -- internals ---------------------------------------------------------

    async def _get_row(self, session_id: str) -> dict[str, Any] | None:
        return await self.db.fetchone("SELECT * FROM upload_sessions WHERE id = ?", (session_id,))

    async def _delete_row(self, session_id: str) -> None:
        await self.db.execute("DELETE FROM upload_sessions WHERE id = ?", (session_id,))

    async def _count_open_for_user(self, user_id: str) -> int:
        row = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM upload_sessions "
            "WHERE user_id = ? AND status = 'open' AND expires_at > ?",
            (user_id, _iso(_utc_now())),
        )
        return int(row["c"]) if row else 0

    async def _require_open(self, session_id: str) -> UploadSession:
        row = await self._get_row(session_id)
        if row is None:
            raise UploadSessionError(
                "NO_SESSION", f"Session {session_id} not found.", {"session_id": session_id}
            )
        sess = UploadSession.from_row(row)
        if sess.status != "open":
            raise UploadSessionError(
                "BAD_STATE",
                f"Session {session_id} is in state '{sess.status}'.",
                {"state": sess.status},
            )
        if sess.expires_at <= _utc_now():
            raise UploadSessionError(
                "EXPIRED", f"Session {session_id} has expired.", {"session_id": session_id}
            )
        return sess


def _unlink_silent(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        logger.debug("Could not remove spill file %s: %s", path, e)


# --- Singleton + background cleanup ---------------------------------------

_store: UploadSessionStore | None = None


def get_upload_session_store() -> UploadSessionStore:
    global _store
    if _store is None:
        _store = UploadSessionStore()
    return _store


def set_upload_session_store(store: UploadSessionStore | None) -> None:
    """Override the singleton (used by tests)."""
    global _store
    _store = store


class CleanupTask:
    """Periodically reaps expired sessions. Register in server lifespan."""

    def __init__(
        self,
        store: UploadSessionStore | None = None,
        interval_seconds: int = 300,
    ) -> None:
        self._store = store
        self.interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.id = uuid.uuid4().hex[:8]

    @property
    def store(self) -> UploadSessionStore:
        return self._store or get_upload_session_store()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name=f"upload-cleanup-{self.id}")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.store.cleanup_expired()
            except Exception as e:  # noqa: BLE001
                logger.warning("Upload-session cleanup error: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except TimeoutError:
                continue
