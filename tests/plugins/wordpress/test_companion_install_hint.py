"""Tests for the shared ``companion_install_hint`` helper + its use in
companion-backed handlers' ``companion_unreachable`` error payloads.

The helper's job is to give the caller enough information to actually
install / configure the companion plugin rather than just saying
"companion unreachable". Every handler that routes through the
companion now emits this dict alongside the existing human-readable
``hint`` string.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    COMPANION_DOWNLOAD_URL,
    companion_install_hint,
)


@pytest.fixture
def wp_client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.post = AsyncMock(side_effect=RuntimeError("rest_no_route: 404"))
    c.get = AsyncMock(side_effect=RuntimeError("rest_no_route: 404"))
    return c


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


class TestCompanionInstallHintHelper:
    @pytest.mark.unit
    def test_download_url_points_at_github_raw(self):
        assert COMPANION_DOWNLOAD_URL.startswith("https://github.com/airano-ir/mcphub/raw/main/")
        assert COMPANION_DOWNLOAD_URL.endswith("airano-mcp-bridge.zip")

    @pytest.mark.unit
    def test_returns_required_keys(self):
        hint = companion_install_hint(min_version="2.4.0")
        assert set(hint.keys()) == {
            "install_url",
            "install_instructions",
            "required_capability",
            "companion_min_version",
        }
        assert hint["companion_min_version"] == "2.4.0"
        assert hint["required_capability"] == "manage_options"

    @pytest.mark.unit
    def test_capability_override(self):
        hint = companion_install_hint(min_version="2.3.0", required_capability="edit_posts")
        assert hint["required_capability"] == "edit_posts"
        assert "edit_posts" in hint["install_instructions"]

    @pytest.mark.unit
    def test_route_hint_appended_when_provided(self):
        hint = companion_install_hint(min_version="2.8.0", route="airano-mcp/v1/foo")
        assert hint["route"] == "airano-mcp/v1/foo"

    @pytest.mark.unit
    def test_install_url_is_stable(self):
        hint_a = companion_install_hint(min_version="2.0.0")
        hint_b = companion_install_hint(min_version="3.0.0")
        # The download URL itself is version-agnostic — it always points
        # at the latest zip on main.
        assert hint_a["install_url"] == hint_b["install_url"] == COMPANION_DOWNLOAD_URL


# ---------------------------------------------------------------------------
# End-to-end: a handler emits install_hint when the companion is missing.
# ---------------------------------------------------------------------------


class TestHandlerEmitsInstallHint:
    @pytest.mark.asyncio
    async def test_cache_purge_emits_install_hint_on_failure(self, wp_client):
        from plugins.wordpress.handlers.cache_purge import CachePurgeHandler

        handler = CachePurgeHandler(wp_client)
        out = json.loads(await handler.cache_purge())
        assert out["ok"] is False
        assert out["error"] == "companion_unreachable"
        assert "install_hint" in out
        assert out["install_hint"]["install_url"] == COMPANION_DOWNLOAD_URL
        assert out["install_hint"]["companion_min_version"] == "2.4.0"
        assert out["install_hint"]["required_capability"] == "manage_options"
        assert out["install_hint"]["route"] == "airano-mcp/v1/cache-purge"

    @pytest.mark.asyncio
    async def test_regenerate_thumbnails_emits_install_hint(self, wp_client):
        from plugins.wordpress.handlers.regenerate_thumbnails import (
            RegenerateThumbnailsHandler,
        )

        handler = RegenerateThumbnailsHandler(wp_client)
        out = json.loads(await handler.regenerate_thumbnails(ids=[1, 2]))
        assert out["error"] == "companion_unreachable"
        assert out["install_hint"]["companion_min_version"] == "2.8.0"
        # Writes need upload_files, not manage_options.
        assert out["install_hint"]["required_capability"] == "upload_files"

    @pytest.mark.asyncio
    async def test_bulk_meta_emits_install_hint(self, wp_client):
        from plugins.wordpress.handlers.bulk_meta import BulkMetaHandler

        handler = BulkMetaHandler(wp_client)
        out = json.loads(
            await handler.bulk_update_meta(updates=[{"post_id": 1, "meta": {"k": "v"}}])
        )
        assert out["error"] == "companion_unreachable"
        assert out["install_hint"]["companion_min_version"] == "2.2.0"

    @pytest.mark.asyncio
    async def test_export_emits_install_hint(self, wp_client):
        from plugins.wordpress.handlers.export import ExportHandler

        handler = ExportHandler(wp_client)
        out = json.loads(await handler.export_content())
        assert out["error"] == "companion_unreachable"
        assert out["install_hint"]["companion_min_version"] == "2.3.0"
        # Export uses edit_posts, not manage_options.
        assert out["install_hint"]["required_capability"] == "edit_posts"

    @pytest.mark.asyncio
    async def test_site_health_emits_install_hint(self, wp_client):
        from plugins.wordpress.handlers.site_health import SiteHealthHandler

        handler = SiteHealthHandler(wp_client)
        out = json.loads(await handler.site_health())
        assert out["error"] == "companion_unreachable"
        assert out["install_hint"]["companion_min_version"] == "2.6.0"

    @pytest.mark.asyncio
    async def test_transient_flush_emits_install_hint(self, wp_client):
        from plugins.wordpress.handlers.transient_flush import TransientFlushHandler

        handler = TransientFlushHandler(wp_client)
        out = json.loads(await handler.transient_flush())
        assert out["error"] == "companion_unreachable"
        assert out["install_hint"]["companion_min_version"] == "2.5.0"

    @pytest.mark.asyncio
    async def test_capabilities_probe_embeds_install_hint_when_empty(self, wp_client):
        """``_empty_capabilities_payload`` is the fallback shape every
        companion probe returns on failure; the install hint must be in
        there too so the UI can link-to-install without a second lookup."""
        from plugins.wordpress.handlers.capabilities import _empty_capabilities_payload

        payload = _empty_capabilities_payload("https://wp.example.com", reason="test")
        assert "install_hint" in payload
        assert payload["install_hint"]["install_url"] == COMPANION_DOWNLOAD_URL
