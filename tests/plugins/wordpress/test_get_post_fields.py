"""F.X.fix #4 — get_post default projection + strict ``fields=`` allow-list.

Regression: ``get_post`` dropped ``featured_media``, ``slug``, and
``featured_media_url`` from its response even when callers asked for
them explicitly via ``fields=``. Fix restores the defaults and makes
the ``fields`` parameter a strict allow-list rather than a subset of a
hard-coded projection.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.handlers.posts import PostsHandler

SAMPLE_POST = {
    "id": 42,
    "slug": "mcp-hub-launch",
    "featured_media": 77,
    "title": {"rendered": "MCP Hub Launch"},
    "content": {"rendered": "<p>Hello world</p>"},
    "excerpt": {"rendered": "<p>short</p>"},
    "status": "publish",
    "date": "2026-04-17T10:00:00",
    "modified": "2026-04-17T10:05:00",
    "categories": [3],
    "tags": [9],
    "meta": {
        "rank_math_title": "MCP Hub SEO",
        "rank_math_description": "Self-hosted MCP tools",
        "private_key_not_registered": "not returned by real REST",
    },
    "link": "https://example.com/mcp-hub-launch",
    "_embedded": {
        "author": [{"name": "Ali"}],
        "wp:featuredmedia": [
            {
                "id": 77,
                "source_url": "https://example.com/wp-content/uploads/hero.webp",
            }
        ],
    },
}

SAMPLE_PAGE = {
    "id": 87,
    "slug": "about",
    "parent": 0,
    "featured_media": 99,
    "title": {"rendered": "About"},
    "content": {"rendered": "<p>About page content</p>"},
    "excerpt": {"rendered": "<p>About excerpt</p>"},
    "status": "publish",
    "date": "2026-05-31T10:00:00",
    "modified": "2026-05-31T10:05:00",
    "meta": {
        "_yoast_wpseo_metadesc": "About page description",
        "rank_math_title": "About SEO",
    },
    "link": "https://example.com/about/",
    "_embedded": {
        "author": [{"name": "Sara"}],
        "wp:featuredmedia": [
            {
                "id": 99,
                "source_url": "https://example.com/wp-content/uploads/about.webp",
            }
        ],
    },
}


@pytest.fixture
def handler_with(post_payload):
    client = AsyncMock()
    client.get = AsyncMock(return_value=post_payload)
    return PostsHandler(client), client


class TestDefaultProjection:
    @pytest.mark.asyncio
    async def test_default_response_includes_featured_media_slug_and_url(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_POST)
        handler = PostsHandler(client)

        raw = await handler.get_post(post_id=42)
        data = json.loads(raw)

        assert data["id"] == 42
        assert data["slug"] == "mcp-hub-launch"
        assert data["featured_media"] == 77
        assert data["featured_media_url"] == "https://example.com/wp-content/uploads/hero.webp"

    @pytest.mark.asyncio
    async def test_featured_media_url_empty_when_no_embedded_media(self):
        post = {**SAMPLE_POST, "featured_media": 0, "_embedded": {"author": [{"name": "x"}]}}
        client = AsyncMock()
        client.get = AsyncMock(return_value=post)
        handler = PostsHandler(client)

        raw = await handler.get_post(post_id=42)
        data = json.loads(raw)

        assert data["featured_media"] == 0
        assert data["featured_media_url"] == ""

    @pytest.mark.asyncio
    async def test_default_still_embeds_metadata(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_POST)
        handler = PostsHandler(client)

        await handler.get_post(post_id=42)
        # ``_embed=true`` must remain in query so featured_media_url can
        # be derived from _embedded.wp:featuredmedia.
        call = client.get.call_args
        params = call.kwargs.get("params") or call.args[1]
        assert params.get("_embed") == "true"


class TestStrictFieldsAllowList:
    @pytest.mark.asyncio
    async def test_fields_limits_to_requested_plus_id(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_POST)
        handler = PostsHandler(client)

        raw = await handler.get_post(post_id=42, fields="slug,featured_media")
        data = json.loads(raw)
        # id is always preserved for identification.
        assert set(data.keys()) == {"id", "slug", "featured_media"}

    @pytest.mark.asyncio
    async def test_fields_title_only_excludes_slug_by_design(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_POST)
        handler = PostsHandler(client)

        raw = await handler.get_post(post_id=42, fields="title")
        data = json.loads(raw)
        # Previous behaviour implicitly included slug even when NOT
        # requested — strict allow-list must drop it.
        assert "slug" not in data
        assert "featured_media" not in data
        assert set(data.keys()) == {"id", "title"}

    @pytest.mark.asyncio
    async def test_fields_featured_media_url_honoured(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_POST)
        handler = PostsHandler(client)

        raw = await handler.get_post(post_id=42, fields="featured_media_url")
        data = json.loads(raw)
        assert set(data.keys()) == {"id", "featured_media_url"}
        assert data["featured_media_url"].startswith("https://")

    @pytest.mark.asyncio
    async def test_unknown_field_name_is_ignored(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_POST)
        handler = PostsHandler(client)

        raw = await handler.get_post(post_id=42, fields="slug,does_not_exist")
        data = json.loads(raw)
        # Unknown name silently dropped; requested known names plus id.
        assert set(data.keys()) == {"id", "slug"}

    @pytest.mark.asyncio
    async def test_fields_passes_wp_fields_query_param(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_POST)
        handler = PostsHandler(client)

        await handler.get_post(post_id=42, fields="featured_media,slug")
        call = client.get.call_args
        params = call.kwargs.get("params") or call.args[1]
        wp_fields = set((params.get("_fields") or "").split(","))
        assert "featured_media" in wp_fields
        assert "slug" in wp_fields
        assert "id" in wp_fields

    @pytest.mark.asyncio
    async def test_fields_can_read_back_rest_meta(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_POST)
        handler = PostsHandler(client)

        raw = await handler.get_post(
            post_id=42,
            fields="id,meta",
            meta_keys="rank_math_title,rank_math_description",
        )
        data = json.loads(raw)

        assert set(data.keys()) == {"id", "meta"}
        assert data["meta"] == {
            "rank_math_title": "MCP Hub SEO",
            "rank_math_description": "Self-hosted MCP tools",
        }
        params = client.get.call_args.kwargs["params"]
        wp_fields = set((params.get("_fields") or "").split(","))
        assert {"id", "meta"}.issubset(wp_fields)


class TestGetPage:
    @pytest.mark.asyncio
    async def test_get_page_uses_pages_endpoint(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_PAGE)
        handler = PostsHandler(client)

        raw = await handler.get_page(page_id=87)
        data = json.loads(raw)

        assert data["id"] == 87
        assert data["slug"] == "about"
        assert data["featured_media"] == 99
        assert data["featured_media_url"].endswith("/about.webp")

        client.get.assert_called_once()
        endpoint = client.get.call_args.args[0]
        params = client.get.call_args.kwargs["params"]
        assert endpoint == "pages/87"
        assert params["_embed"] == "true"

    @pytest.mark.asyncio
    async def test_get_page_fields_are_strict(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_PAGE)
        handler = PostsHandler(client)

        raw = await handler.get_page(page_id=87, fields="slug,parent")
        data = json.loads(raw)

        assert set(data.keys()) == {"id", "slug", "parent"}
        params = client.get.call_args.kwargs["params"]
        wp_fields = set((params.get("_fields") or "").split(","))
        assert {"id", "slug", "parent"}.issubset(wp_fields)

    @pytest.mark.asyncio
    async def test_get_page_can_filter_meta_keys(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=SAMPLE_PAGE)
        handler = PostsHandler(client)

        raw = await handler.get_page(
            page_id=87,
            fields="id,meta",
            meta_keys="_yoast_wpseo_metadesc",
        )
        data = json.loads(raw)

        assert data == {
            "id": 87,
            "meta": {"_yoast_wpseo_metadesc": "About page description"},
        }
