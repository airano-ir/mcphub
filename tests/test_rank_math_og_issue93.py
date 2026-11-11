"""Issue #93: Rank Math identity sync + Open Graph image variant.

Root cause established on the live post: Rank Math reported og:image
1024x1024 *correctly* — the AI cover itself was square. The fix is a real
1200x630 crop for social cards (opt-in), pointed at by Rank Math's Facebook
image meta, plus a companion route that pushes the site name into Rank Math's
schema identity (captured once by its wizard).
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from plugins.ai_image.providers.base import GenerationResult
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.ai_media import OG_SIZE, AIMediaHandler, make_og_variant
from plugins.wordpress_specialist.handlers.site_config import SiteConfigHandler

pytestmark = pytest.mark.unit


def _png(size=(1024, 1024), mode="RGB") -> bytes:
    buf = io.BytesIO()
    color = (30, 60, 200, 128) if mode == "RGBA" else (30, 60, 200)
    Image.new(mode, size, color).save(buf, "PNG")
    return buf.getvalue()


def test_square_cover_becomes_1200x630_jpeg():
    out = make_og_variant(_png((1024, 1024)))
    with Image.open(io.BytesIO(out)) as im:
        assert im.size == OG_SIZE == (1200, 630)
        assert im.format == "JPEG"


def test_transparent_png_is_flattened():
    out = make_og_variant(_png((800, 800), mode="RGBA"))
    with Image.open(io.BytesIO(out)) as im:
        assert im.mode == "RGB" and im.size == (1200, 630)


class _StubProvider:
    def __init__(self, result):
        self._result = result

    async def generate(self, api_key, request):
        return self._result


def _client_post_router(saved_meta: bool):
    async def post(endpoint, json_data=None, **_):
        if endpoint == "posts/5" and "meta" in (json_data or {}):
            meta = json_data["meta"] if saved_meta else {}
            return {"id": 5, "meta": meta}
        return {"id": 42}

    return AsyncMock(side_effect=post)


async def _run(monkeypatch, *, saved_meta: bool):
    client = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    handler = AIMediaHandler(client, user_id="u1")
    monkeypatch.setattr(handler, "_resolve_api_key", AsyncMock(return_value="sk"))
    result = GenerationResult(
        data=_png((1024, 1024)), mime="image/png", filename="cover.png", meta={}, cost_usd=0.0
    )
    monkeypatch.setattr(
        "plugins.wordpress.handlers.ai_media.get_provider", lambda _: _StubProvider(result)
    )
    uploads = AsyncMock(
        side_effect=[
            {"id": 42, "source_url": "https://wp.example.com/cover.png", "mime_type": "image/png"},
            {
                "id": 43,
                "source_url": "https://wp.example.com/cover-og-1200x630.jpg",
                "mime_type": "image/jpeg",
            },
        ]
    )
    monkeypatch.setattr("plugins.wordpress.handlers.ai_media.wp_raw_upload", uploads)
    monkeypatch.setattr(
        "plugins.wordpress.handlers.ai_media._apply_metadata_and_attach",
        AsyncMock(return_value={"metadata_applied": True, "featured_set": True}),
    )
    client.post = _client_post_router(saved_meta)
    out = json.loads(
        await handler.generate_and_upload_image(
            provider="openai",
            prompt="cover",
            attach_to_post=5,
            set_featured=True,
            skip_optimize=True,
            generate_og_variant=True,
        )
    )
    return out, uploads, client


async def test_og_variant_uploaded_and_rank_math_pointed_at_it(monkeypatch):
    out, uploads, client = await _run(monkeypatch, saved_meta=True)
    assert out["id"] == 42  # original stays the main / featured image
    og = out["og_variant"]
    assert og["media_id"] == 43 and og["width"] == 1200 and og["height"] == 630
    assert og["rank_math_og_set"] is True
    second = uploads.await_args_list[1]
    assert second.kwargs["mime_hint"] == "image/jpeg"
    assert second.kwargs["filename"] == "cover-og-1200x630.jpg"
    assert second.kwargs["idempotency_key"].endswith(":og")
    with Image.open(io.BytesIO(second.args[1])) as im:
        assert im.size == (1200, 630)
    meta_call = [c for c in client.post.await_args_list if c.args[0] == "posts/5"][0]
    assert meta_call.kwargs["json_data"]["meta"]["rank_math_facebook_image_id"] == 43


async def test_missing_companion_meta_is_a_warning_not_a_failure(monkeypatch):
    out, _, _ = await _run(monkeypatch, saved_meta=False)
    assert out["og_variant"]["rank_math_og_set"] is False
    assert any("Rank Math OG image meta was not saved" in w for w in out["warnings"])


async def test_default_off_keeps_single_upload(monkeypatch):
    client = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    handler = AIMediaHandler(client, user_id="u1")
    monkeypatch.setattr(handler, "_resolve_api_key", AsyncMock(return_value="sk"))
    result = GenerationResult(
        data=_png(), mime="image/png", filename="a.png", meta={}, cost_usd=0.0
    )
    monkeypatch.setattr(
        "plugins.wordpress.handlers.ai_media.get_provider", lambda _: _StubProvider(result)
    )
    uploads = AsyncMock(return_value={"id": 7, "source_url": "u", "mime_type": "image/png"})
    monkeypatch.setattr("plugins.wordpress.handlers.ai_media.wp_raw_upload", uploads)
    out = json.loads(
        await handler.generate_and_upload_image(provider="openai", prompt="x", skip_optimize=True)
    )
    assert "og_variant" not in out and uploads.await_count == 1


# ------------------------------------------------- Rank Math identity sync


async def test_sync_identity_posts_to_companion():
    client = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    client.post = AsyncMock(
        return_value={"updated": True, "before": {"website_name": "blog"}, "after": {}}
    )
    out = await SiteConfigHandler(client).wp_rank_math_sync_identity(name="PaleBlueDot Blog")
    assert out["updated"] is True
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/seo/rank-math/sync-identity",
        json_data={"name": "PaleBlueDot Blog"},
        use_custom_namespace=True,
    )


async def test_sync_identity_old_companion_gives_upgrade_hint():
    client = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    client.post = AsyncMock(side_effect=Exception("[NOT_FOUND] rest_no_route"))
    out = await SiteConfigHandler(client).wp_rank_math_sync_identity()
    assert out["error_code"] == "COMPANION_UPGRADE_REQUIRED"


def test_companion_registers_the_route_and_version():
    php = Path("wordpress-plugin/airano-mcp-bridge/airano-mcp-bridge.php").read_text(
        encoding="utf-8"
    )
    assert "'/admin/seo/rank-math/sync-identity'" in php
    assert "function handle_admin_rank_math_sync_identity" in php
    # The route landed in companion 2.21.0; later companions still carry it.
    declared = re.search(r"const VERSION = '(\d+)\.(\d+)\.(\d+)';", php)
    assert declared, "companion declares no VERSION"
    assert tuple(int(part) for part in declared.groups()) >= (2, 21, 0)
    # the handler must only touch Rank Math's identity keys
    body = php.split("function handle_admin_rank_math_sync_identity", 1)[1].split(
        "public function", 1
    )[0]
    assert "update_option('rank-math-options-titles', $titles)" in body
    assert body.count("update_option(") == 1
