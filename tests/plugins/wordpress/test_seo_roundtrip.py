"""F.X.fix #2 — Rank Math SEO roundtrip: write → read → assert equality.

Protects against the regression where ``update_post_seo`` wrote
``rank_math_seo_title`` (wrong key) while ``get_post_seo`` read back
from the same wrong key, so a full write→read cycle looked successful
but the WordPress frontend showed no SEO title because Rank Math never
saw the value.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.handlers.seo import SEOHandler


@pytest.fixture
def fake_wp_state():
    """In-memory meta store shared across fake client get/post calls.

    Rank Math is considered active when at least one canonical
    rank_math_* key exists in the store, which mirrors the real
    _check_seo_plugins detection heuristic.
    """
    return {
        "meta": {
            # Seeded so _check_seo_plugins detects Rank Math as active.
            "rank_math_focus_keyword": "",
            "rank_math_title": "",
            "rank_math_description": "",
        }
    }


@pytest.fixture
def fake_client(fake_wp_state):
    client = AsyncMock()

    async def _get(endpoint, params=None, use_custom_namespace=False, use_woocommerce=False):
        if endpoint.startswith("posts/"):
            return {
                "id": 42,
                "title": {"rendered": "Test Post"},
                "meta": dict(fake_wp_state["meta"]),
            }
        if endpoint == "posts":
            return [
                {
                    "id": 42,
                    "title": {"rendered": "Test Post"},
                    "meta": dict(fake_wp_state["meta"]),
                }
            ]
        raise AssertionError(f"unexpected GET {endpoint}")

    async def _post(endpoint, json_data=None, **_):
        if endpoint.startswith("posts/") and json_data and "meta" in json_data:
            fake_wp_state["meta"].update(json_data["meta"])
            return {"id": 42, "meta": dict(fake_wp_state["meta"])}
        raise AssertionError(f"unexpected POST {endpoint}")

    client.get = _get
    client.post = _post
    return client


class TestRankMathRoundtrip:
    @pytest.mark.asyncio
    async def test_update_writes_canonical_rank_math_title(self, fake_client, fake_wp_state):
        handler = SEOHandler(fake_client)
        # Force the bridge-status fallback path to detect Rank Math via
        # meta heuristic (seeded in fixture).
        raw = await handler.update_post_seo(
            post_id=42,
            focus_keyword="mcp hub",
            seo_title="MCP Hub — unified MCP server",
            meta_description="Self-hosted MCP platform",
        )
        resp = json.loads(raw)
        assert "rank_math_title" in resp["updated_fields"]
        # The wrong key must NOT be written — guards against silent
        # regression of the rank_math_seo_title bug.
        assert "rank_math_seo_title" not in resp["updated_fields"]
        assert fake_wp_state["meta"]["rank_math_title"] == "MCP Hub — unified MCP server"
        assert fake_wp_state["meta"]["rank_math_focus_keyword"] == "mcp hub"
        assert fake_wp_state["meta"]["rank_math_description"] == "Self-hosted MCP platform"

    @pytest.mark.asyncio
    async def test_get_reads_canonical_rank_math_title(self, fake_client, fake_wp_state):
        fake_wp_state["meta"].update(
            {
                "rank_math_focus_keyword": "mcp hub",
                "rank_math_title": "Readback Title",
                "rank_math_description": "Readback Desc",
            }
        )
        handler = SEOHandler(fake_client)
        raw = await handler.get_post_seo(post_id=42)
        data = json.loads(raw)
        assert data["plugin_detected"] == "rank_math"
        assert data["seo_title"] == "Readback Title"
        assert data["focus_keyword"] == "mcp hub"
        assert data["meta_description"] == "Readback Desc"

    @pytest.mark.asyncio
    async def test_roundtrip_write_then_read_returns_non_empty(self, fake_client, fake_wp_state):
        handler = SEOHandler(fake_client)
        await handler.update_post_seo(
            post_id=42,
            focus_keyword="kw",
            seo_title="Title A",
            meta_description="Desc A",
        )
        raw = await handler.get_post_seo(post_id=42)
        data = json.loads(raw)
        # Every field we just wrote must come back non-empty.
        assert data["focus_keyword"] == "kw"
        assert data["seo_title"] == "Title A"
        assert data["meta_description"] == "Desc A"
