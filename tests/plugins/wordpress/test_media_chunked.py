"""Tests for F.5a.5 chunked media upload (session store + WP handler)."""

from __future__ import annotations

import asyncio
import base64 as _b64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.database import Database
from core.upload_sessions import (
    CleanupTask,
    UploadSessionError,
    UploadSessionStore,
    make_session_id,
    set_upload_session_store,
)
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.media_chunked import MediaChunkedHandler

_PNG_1x1 = _b64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _client() -> WordPressClient:
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
async def db(tmp_path: Path):
    d = Database(str(tmp_path / "test.db"))
    await d.initialize()
    try:
        yield d
    finally:
        await d.close()


@pytest.fixture
async def store(tmp_path: Path, db: Database) -> UploadSessionStore:
    s = UploadSessionStore(db=db, spill_dir=tmp_path / "spill")
    set_upload_session_store(s)
    try:
        yield s
    finally:
        set_upload_session_store(None)


@pytest.fixture
def handler(store: UploadSessionStore) -> MediaChunkedHandler:
    return MediaChunkedHandler(_client(), user_id="alice", store=store)


def _wp_response_mock(wp_response: dict):
    mock_resp = AsyncMock()
    mock_resp.status = 201
    mock_resp.text = AsyncMock(return_value=json.dumps(wp_response))
    mock_resp.json = AsyncMock(return_value=wp_response)
    mock_sess = AsyncMock()
    mock_sess.post = lambda *a, **kw: AsyncMock(
        __aenter__=AsyncMock(return_value=mock_resp),
        __aexit__=AsyncMock(return_value=False),
    )
    cls_mock = AsyncMock(
        __aenter__=AsyncMock(return_value=mock_sess),
        __aexit__=AsyncMock(return_value=False),
    )
    return cls_mock


class TestSessionStoreBasics:
    @pytest.mark.asyncio
    async def test_deterministic_session_id(self):
        a = make_session_id("u1", "a.bin", 100, None, None)
        b = make_session_id("u1", "a.bin", 100, None, None)
        c = make_session_id("u2", "a.bin", 100, None, None)
        assert a == b
        assert a != c

    @pytest.mark.asyncio
    async def test_start_creates_row_and_spill(self, store: UploadSessionStore):
        sess = await store.start(user_id="alice", filename="f.bin", total_bytes=10)
        assert sess.status == "open"
        assert sess.spill_path.exists()
        assert sess.received_bytes == 0

    @pytest.mark.asyncio
    async def test_start_is_idempotent_for_same_tuple(self, store: UploadSessionStore):
        s1 = await store.start(user_id="alice", filename="f.bin", total_bytes=10)
        s2 = await store.start(user_id="alice", filename="f.bin", total_bytes=10)
        assert s1.id == s2.id

    @pytest.mark.asyncio
    async def test_hard_cap_rejects(self, store: UploadSessionStore):
        store.max_session_bytes = 1024
        with pytest.raises(UploadSessionError) as e:
            await store.start(user_id="alice", filename="big.bin", total_bytes=2048)
        assert e.value.code == "SESSION_TOO_LARGE"


class TestAppendAndFinalize:
    @pytest.mark.asyncio
    async def test_round_trip_two_chunks(self, store: UploadSessionStore):
        payload = b"abcdefghij"  # 10 bytes
        sess = await store.start(user_id="alice", filename="f.bin", total_bytes=10)
        await store.append_chunk(sess.id, 0, payload[:6])
        await store.append_chunk(sess.id, 1, payload[6:])
        sess2, data = await store.finalize(sess.id)
        assert data == payload
        assert not sess2.spill_path.exists()

    @pytest.mark.asyncio
    async def test_chunk_out_of_order(self, store: UploadSessionStore):
        sess = await store.start(user_id="alice", filename="f.bin", total_bytes=10)
        await store.append_chunk(sess.id, 0, b"abcde")
        with pytest.raises(UploadSessionError) as e:
            await store.append_chunk(sess.id, 2, b"fgh")
        assert e.value.code == "CHUNK_ORDER"

    @pytest.mark.asyncio
    async def test_chunk_overflow(self, store: UploadSessionStore):
        sess = await store.start(user_id="alice", filename="f.bin", total_bytes=5)
        with pytest.raises(UploadSessionError) as e:
            await store.append_chunk(sess.id, 0, b"toolongdata")
        assert e.value.code == "CHUNK_OVERFLOW"

    @pytest.mark.asyncio
    async def test_finalize_sha_mismatch_keeps_session(self, store: UploadSessionStore):
        payload = b"hello world"
        wrong = hashlib.sha256(b"other").hexdigest()
        sess = await store.start(
            user_id="alice",
            filename="f.bin",
            total_bytes=len(payload),
            sha256=wrong,
        )
        await store.append_chunk(sess.id, 0, payload)
        with pytest.raises(UploadSessionError) as e:
            await store.finalize(sess.id)
        assert e.value.code == "CHECKSUM_MISMATCH"
        # Session still present — spill file still on disk
        again = await store.get(sess.id)
        assert again is not None
        assert again.spill_path.exists()

    @pytest.mark.asyncio
    async def test_finalize_sha_match_passes(self, store: UploadSessionStore):
        payload = b"hello world"
        digest = hashlib.sha256(payload).hexdigest()
        sess = await store.start(
            user_id="alice",
            filename="f.bin",
            total_bytes=len(payload),
            sha256=digest,
        )
        await store.append_chunk(sess.id, 0, payload)
        _, data = await store.finalize(sess.id)
        assert data == payload

    @pytest.mark.asyncio
    async def test_abort_removes_spill(self, store: UploadSessionStore):
        sess = await store.start(user_id="alice", filename="f.bin", total_bytes=10)
        spill = sess.spill_path
        assert spill.exists()
        assert await store.abort(sess.id) is True
        assert not spill.exists()
        assert await store.get(sess.id) is None


class TestQuotaAndCleanup:
    @pytest.mark.asyncio
    async def test_quota_rejects_11th_session(self, store: UploadSessionStore):
        store.max_concurrent_per_user = 10
        ids = set()
        for i in range(10):
            s = await store.start(user_id="bob", filename=f"f{i}.bin", total_bytes=10)
            ids.add(s.id)
        assert len(ids) == 10
        with pytest.raises(UploadSessionError) as e:
            await store.start(user_id="bob", filename="f10.bin", total_bytes=10)
        assert e.value.code == "QUOTA_EXCEEDED"

    @pytest.mark.asyncio
    async def test_cleanup_reaps_expired(self, store: UploadSessionStore, db: Database):
        sess = await store.start(user_id="alice", filename="f.bin", total_bytes=10)
        spill = sess.spill_path
        # Force-expire via DB update
        past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        await db.execute("UPDATE upload_sessions SET expires_at = ? WHERE id = ?", (past, sess.id))
        reaped = await store.cleanup_expired()
        assert reaped == 1
        assert not spill.exists()
        assert await store.get(sess.id) is None

    @pytest.mark.asyncio
    async def test_cleanup_task_runs(self, store: UploadSessionStore, db: Database):
        sess = await store.start(user_id="alice", filename="f.bin", total_bytes=10)
        past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        await db.execute("UPDATE upload_sessions SET expires_at = ? WHERE id = ?", (past, sess.id))
        task = CleanupTask(store=store, interval_seconds=60)
        await task.start()
        # Give the loop a tick to run its first iteration.
        for _ in range(20):
            if await store.get(sess.id) is None:
                break
            await asyncio.sleep(0.05)
        await task.stop()
        assert await store.get(sess.id) is None


class TestHandlerIntegration:
    @pytest.mark.asyncio
    async def test_handler_round_trip_calls_wp_once(self, handler: MediaChunkedHandler):
        payload = _PNG_1x1
        # Start
        start_out = json.loads(
            await handler.upload_media_chunked_start(filename="photo.png", total_bytes=len(payload))
        )
        sid = start_out["session_id"]
        half = len(payload) // 2
        c0 = _b64.b64encode(payload[:half]).decode()
        c1 = _b64.b64encode(payload[half:]).decode()
        await handler.upload_media_chunked_chunk(sid, 0, c0)
        await handler.upload_media_chunked_chunk(sid, 1, c1)

        wp_response = {
            "id": 999,
            "title": {"rendered": "photo"},
            "source_url": "https://wp.example.com/photo.png",
            "mime_type": "image/png",
            "media_type": "image",
        }
        with patch("plugins.wordpress.handlers._media_core.aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = _wp_response_mock(wp_response)
            out = json.loads(await handler.upload_media_chunked_finish(session_id=sid))
            # No metadata/attach args → only the raw-upload ClientSession() call
            assert mock_cls.call_count == 1
        assert out["id"] == 999
        assert out["source"] == "chunked"

    @pytest.mark.asyncio
    async def test_handler_abort(self, handler: MediaChunkedHandler):
        start_out = json.loads(
            await handler.upload_media_chunked_start(filename="f.bin", total_bytes=10)
        )
        sid = start_out["session_id"]
        out = json.loads(await handler.upload_media_chunked_abort(sid))
        assert out["aborted"] is True

    @pytest.mark.asyncio
    async def test_handler_chunk_order_returns_error_json(self, handler: MediaChunkedHandler):
        start_out = json.loads(
            await handler.upload_media_chunked_start(filename="f.bin", total_bytes=10)
        )
        sid = start_out["session_id"]
        chunk_b64 = _b64.b64encode(b"abc").decode()
        out = json.loads(await handler.upload_media_chunked_chunk(sid, 5, chunk_b64))
        assert out["error_code"] == "CHUNK_ORDER"
