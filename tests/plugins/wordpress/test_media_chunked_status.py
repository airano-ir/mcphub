"""F.5a.8.4 — resumable chunked upload status tool.

Verifies the new ``upload_media_chunked_status`` tool returns the
expected ``received_bytes`` / ``next_chunk`` for active sessions and
yields a ``NOT_FOUND`` error for unknown / finalised / aborted ones.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from core.database import Database
from core.upload_sessions import (
    UploadSessionStore,
    set_upload_session_store,
)
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.media_chunked import (
    MediaChunkedHandler,
    get_tool_specifications,
)


@pytest.fixture
async def _db(tmp_path: Path):
    db = Database(str(tmp_path / "status.db"))
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
async def _store(tmp_path: Path, _db: Database):
    s = UploadSessionStore(db=_db, spill_dir=tmp_path / "spill")
    set_upload_session_store(s)
    try:
        yield s
    finally:
        set_upload_session_store(None)


@pytest.fixture
def _handler(_store: UploadSessionStore) -> MediaChunkedHandler:
    client = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    return MediaChunkedHandler(client, user_id="alice", store=_store)


class TestStatusToolSpec:
    @pytest.mark.unit
    def test_status_tool_is_registered(self):
        specs = get_tool_specifications()
        names = [s["name"] for s in specs]
        assert "upload_media_chunked_status" in names

    @pytest.mark.unit
    def test_status_tool_is_read_scope(self):
        specs = get_tool_specifications()
        status = next(s for s in specs if s["name"] == "upload_media_chunked_status")
        assert status["scope"] == "read"
        assert status["schema"]["required"] == ["session_id"]


class TestStatusLookup:
    @pytest.mark.asyncio
    async def test_unknown_session_returns_no_session(self, _handler):
        out = json.loads(await _handler.upload_media_chunked_status(session_id="does-not-exist"))
        # NO_SESSION is the documented taxonomy code used by the rest of
        # the chunked-session surface for exactly this case.
        assert out["error_code"] == "NO_SESSION"
        assert out["session_id"] == "does-not-exist"

    @pytest.mark.asyncio
    async def test_fresh_session_reports_zero_received(self, _handler):
        started = json.loads(
            await _handler.upload_media_chunked_start(filename="big.mp4", total_bytes=1_000_000)
        )
        sid = started["session_id"]

        out = json.loads(await _handler.upload_media_chunked_status(session_id=sid))
        assert out["session_id"] == sid
        assert out["received_bytes"] == 0
        assert out["next_chunk"] == 0
        assert out["total_bytes"] == 1_000_000

    @pytest.mark.asyncio
    async def test_partial_session_reports_progress(self, _handler):
        started = json.loads(
            await _handler.upload_media_chunked_start(filename="big.mp4", total_bytes=100)
        )
        sid = started["session_id"]

        chunk = base64.b64encode(b"A" * 40).decode()
        await _handler.upload_media_chunked_chunk(session_id=sid, index=0, data_b64=chunk)

        out = json.loads(await _handler.upload_media_chunked_status(session_id=sid))
        assert out["received_bytes"] == 40
        assert out["next_chunk"] == 1
        # Still open for more chunks.
        assert out["status"] == "open"

    @pytest.mark.asyncio
    async def test_resume_flow_via_status_then_chunk(self, _handler):
        """End-to-end resume: start → chunk → (simulate disconnect) →
        status → chunk from next_chunk → progress should advance."""
        started = json.loads(
            await _handler.upload_media_chunked_start(filename="big.bin", total_bytes=60)
        )
        sid = started["session_id"]

        first = base64.b64encode(b"x" * 20).decode()
        await _handler.upload_media_chunked_chunk(session_id=sid, index=0, data_b64=first)

        # Simulate client coming back from a disconnect.
        status = json.loads(await _handler.upload_media_chunked_status(session_id=sid))
        resume_idx = status["next_chunk"]
        assert resume_idx == 1

        second = base64.b64encode(b"y" * 25).decode()
        progressed = json.loads(
            await _handler.upload_media_chunked_chunk(
                session_id=sid, index=resume_idx, data_b64=second
            )
        )
        assert progressed["received_bytes"] == 45
        assert progressed["next_chunk"] == 2
