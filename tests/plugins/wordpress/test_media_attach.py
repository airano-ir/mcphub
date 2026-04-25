"""Tests for F.5a.3 WooCommerce attachment + featured-image tool."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.media_attach import (
    MediaAttachHandler,
    _merge_product_images,
)

_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


# --- Pure merge logic -------------------------------------------------------


class TestMergeImages:
    def test_append_gallery_preserves_existing(self):
        out = _merge_product_images([{"id": 1}, {"id": 2}], [3, 4], role="gallery", mode="append")
        assert [i["id"] for i in out] == [1, 2, 3, 4]

    def test_append_gallery_dedupes(self):
        out = _merge_product_images([{"id": 1}, {"id": 2}], [2, 3], role="gallery", mode="append")
        assert [i["id"] for i in out] == [1, 2, 3]

    def test_replace_gallery_keeps_main(self):
        out = _merge_product_images(
            [{"id": 1}, {"id": 2}, {"id": 3}], [9], role="gallery", mode="replace"
        )
        assert [i["id"] for i in out] == [1, 9]

    def test_replace_main_wipes_all(self):
        out = _merge_product_images([{"id": 1}, {"id": 2}], [9], role="main", mode="replace")
        assert [i["id"] for i in out] == [9]

    def test_append_main_promotes_new_to_index0(self):
        out = _merge_product_images([{"id": 1}, {"id": 2}], [9], role="main", mode="append")
        assert out[0]["id"] == 9
        # Existing images demoted but preserved
        assert {i["id"] for i in out} == {9, 1, 2}


# --- Handler integration ----------------------------------------------------


class TestMediaAttachHandler:
    @pytest.mark.asyncio
    async def test_attach_happy_path(self):
        handler = MediaAttachHandler(_client())
        with (
            patch.object(handler.client, "get", new=AsyncMock()) as mock_get,
            patch.object(handler.client, "put", new=AsyncMock()) as mock_put,
        ):
            # media validation GETs + product GET
            mock_get.side_effect = [
                {"id": 10},  # media/10 exists
                {"id": 11},  # media/11 exists
                {"id": 50, "images": [{"id": 1}]},  # products/50
            ]
            mock_put.return_value = {
                "id": 50,
                "images": [{"id": 1, "src": "a"}, {"id": 10, "src": "b"}, {"id": 11, "src": "c"}],
            }
            out = await handler.attach_media_to_product(50, [10, 11], role="gallery", mode="append")
        parsed = json.loads(out)
        assert parsed["product_id"] == 50
        assert [i["id"] for i in parsed["images"]] == [1, 10, 11]
        # Verify PUT body
        put_call = mock_put.await_args
        assert put_call.kwargs["json_data"]["images"] == [{"id": 1}, {"id": 10}, {"id": 11}]
        assert put_call.kwargs["use_woocommerce"] is True

    @pytest.mark.asyncio
    async def test_attach_rejects_missing_media(self):
        handler = MediaAttachHandler(_client())
        with patch.object(handler.client, "get", new=AsyncMock(side_effect=Exception("404"))):
            out = await handler.attach_media_to_product(50, [999])
        assert json.loads(out)["error_code"] == "MEDIA_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_attach_rejects_bad_role(self):
        handler = MediaAttachHandler(_client())
        out = await handler.attach_media_to_product(50, [1], role="invalid")
        assert json.loads(out)["error_code"] == "BAD_ROLE"

    @pytest.mark.asyncio
    async def test_attach_rejects_empty_media_ids(self):
        handler = MediaAttachHandler(_client())
        out = await handler.attach_media_to_product(50, [])
        assert json.loads(out)["error_code"] == "MISSING_FIELD"

    @pytest.mark.asyncio
    async def test_upload_and_attach_base64(self):
        handler = MediaAttachHandler(_client())
        wp_media = {
            "id": 77,
            "title": {"rendered": "x"},
            "source_url": "https://wp.example.com/x.png",
            "mime_type": "image/png",
            "media_type": "image",
        }
        with (
            patch(
                "plugins.wordpress.handlers.media_attach.wp_raw_upload",
                new=AsyncMock(return_value=wp_media),
            ),
            patch(
                "plugins.wordpress.handlers.media_attach.wp_update_media_metadata",
                new=AsyncMock(),
            ),
            patch.object(
                handler.client, "get", new=AsyncMock(return_value={"id": 77, "images": []})
            ),
            patch.object(
                handler.client,
                "put",
                new=AsyncMock(return_value={"id": 50, "images": [{"id": 77, "src": "s"}]}),
            ),
        ):
            out = await handler.upload_and_attach_to_product(
                product_id=50,
                source="base64",
                filename="x.png",
                data=base64.b64encode(_PNG_1x1).decode(),
                role="main",
            )
        parsed = json.loads(out)
        assert parsed["media_id"] == 77
        assert parsed["product_id"] == 50

    @pytest.mark.asyncio
    async def test_set_featured_image_post(self):
        """F.X.fix-pass5 — auto-detects "this is not a WC product",
        falls through to /wp/v2/posts/{id} for regular posts/pages."""
        handler = MediaAttachHandler(_client())

        async def _fake_get(path, **kwargs):
            if kwargs.get("use_woocommerce"):
                raise Exception("404 — not a product")
            return {"id": 9}  # media exists

        with (
            patch.object(handler.client, "get", side_effect=_fake_get),
            patch.object(
                handler.client,
                "post",
                new=AsyncMock(return_value={"id": 100, "featured_media": 9}),
            ) as mock_post,
        ):
            out = await handler.set_featured_image(post_id=100, media_id=9)
        parsed = json.loads(out)
        assert parsed["post_id"] == 100
        assert parsed["featured_media"] == 9
        assert parsed["context"] == "post"
        mock_post.assert_awaited_once_with("posts/100", json_data={"featured_media": 9})

    @pytest.mark.asyncio
    async def test_set_featured_image_wc_product(self):
        """F.X.fix-pass5 — when post_id is a WC product, route through
        WC API (PUT /wc/v3/products/{id} with images[]) instead of
        /wp/v2/posts/{id} which 404s for products."""
        handler = MediaAttachHandler(_client())

        async def _fake_get(path, **kwargs):
            if kwargs.get("use_woocommerce") and path == "products/77":
                return {"id": 77, "images": [{"id": 5}, {"id": 6}]}
            return {"id": 9}  # media exists

        with (
            patch.object(handler.client, "get", side_effect=_fake_get),
            patch.object(
                handler.client,
                "put",
                new=AsyncMock(return_value={"id": 77, "images": [{"id": 9}, {"id": 5}, {"id": 6}]}),
            ) as mock_put,
            patch.object(handler.client, "post", new=AsyncMock()) as mock_post,
        ):
            out = await handler.set_featured_image(post_id=77, media_id=9)
        parsed = json.loads(out)
        assert parsed["post_id"] == 77
        assert parsed["featured_media"] == 9
        assert parsed["context"] == "product"
        # WC PUT was used, NOT /wp/v2/posts.
        mock_put.assert_awaited_once()
        assert mock_put.await_args.kwargs["use_woocommerce"] is True
        assert mock_post.await_count == 0

    @pytest.mark.asyncio
    async def test_upload_and_attach_missing_data(self):
        handler = MediaAttachHandler(_client())
        out = await handler.upload_and_attach_to_product(
            product_id=1, source="base64", filename="x.png"
        )
        assert json.loads(out)["error_code"] == "MISSING_FIELD"

    @pytest.mark.asyncio
    async def test_upload_and_attach_ssrf_blocked(self):
        handler = MediaAttachHandler(_client())
        out = await handler.upload_and_attach_to_product(
            product_id=1,
            source="url",
            filename="x.png",
            url="http://127.0.0.1/x.png",
        )
        assert json.loads(out)["error_code"] == "SSRF"
