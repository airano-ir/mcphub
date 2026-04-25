"""F.X.fix #12 — OpenRouter /v1/models discovery + 1h cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from plugins.ai_image.providers import openrouter as or_mod
from plugins.ai_image.providers.openrouter import OpenRouterProvider


def _fake_resp(*, status, json_data=None, headers=None):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.headers = headers or {}
    return resp


def _mock_session(responses):
    iterator = iter(responses)

    def _request(*_a, **_kw):
        resp = next(iterator)
        return AsyncMock(
            __aenter__=AsyncMock(return_value=resp),
            __aexit__=AsyncMock(return_value=False),
        )

    sess = AsyncMock()
    sess.get = _request
    sess.post = _request
    return sess


def _reset_cache():
    or_mod._models_cache["fetched_at"] = 0.0
    or_mod._models_cache["payload"] = None


@pytest.fixture(autouse=True)
def reset_cache():
    _reset_cache()
    yield
    _reset_cache()


CATALOG_PAYLOAD = {
    "data": [
        {
            "id": "google/gemini-2.5-flash-image",
            "name": "Gemini 2.5 Flash Image",
            "description": "Google's GA image model",
            "context_length": 1000000,
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["image", "text"],
                "modality": "text+image->image+text",
            },
        },
        {
            "id": "google/gemini-2.5-flash-image-preview",
            "name": "Gemini 2.5 Flash Image (Preview)",
            "architecture": {
                "output_modalities": ["image"],
            },
        },
        {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"],
            },
        },
        {
            "id": "openai/dall-e-3",
            "name": "DALL-E 3",
            "architecture": {"output_modalities": ["image"]},
        },
        {
            "id": "meta/llama-3",
            "name": "Llama 3",
            "description": "chat only",
            "architecture": {"output_modalities": ["text"]},
        },
    ]
}


class TestListImageModels:
    @pytest.mark.asyncio
    async def test_filters_to_image_output_only(self):
        provider = OpenRouterProvider()
        resp = _fake_resp(status=200, json_data=CATALOG_PAYLOAD)
        sess = _mock_session([resp])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            models = await provider.list_image_models()
        ids = {m["id"] for m in models}
        # Kept — image output
        assert "google/gemini-2.5-flash-image" in ids
        assert "openai/dall-e-3" in ids
        # Dropped — text-only
        assert "openai/gpt-4o" not in ids
        assert "meta/llama-3" not in ids
        # Dropped — deprecated alias (we refuse to surface it)
        assert "google/gemini-2.5-flash-image-preview" not in ids

    @pytest.mark.asyncio
    async def test_shape_includes_pricing_and_modalities(self):
        provider = OpenRouterProvider()
        resp = _fake_resp(status=200, json_data=CATALOG_PAYLOAD)
        sess = _mock_session([resp])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            models = await provider.list_image_models()
        gemini = next(m for m in models if m["id"] == "google/gemini-2.5-flash-image")
        assert gemini["name"]
        assert "image" in gemini["output_modalities"]
        # F.X.fix #11 integration — catalog exposes price per image for
        # UI display alongside the model list.
        assert gemini["price_per_image_usd"] is not None

    @pytest.mark.asyncio
    async def test_cache_hits_second_call(self):
        provider = OpenRouterProvider()
        resp = _fake_resp(status=200, json_data=CATALOG_PAYLOAD)
        sess = _mock_session([resp])  # only ONE response
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            first = await provider.list_image_models()
            second = await provider.list_image_models()  # cache hit
        assert first == second
        # Second call should not have tried a second HTTP request (mock
        # session would raise StopIteration if it did).

    @pytest.mark.asyncio
    async def test_force_bypasses_cache(self):
        provider = OpenRouterProvider()
        resp1 = _fake_resp(status=200, json_data=CATALOG_PAYLOAD)
        resp2 = _fake_resp(status=200, json_data={"data": []})
        sess = _mock_session([resp1, resp2])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            first = await provider.list_image_models()
            second = await provider.list_image_models(force=True)
        assert len(first) > 0
        assert second == []

    @pytest.mark.asyncio
    async def test_upstream_error_returns_previous_cache(self):
        provider = OpenRouterProvider()
        ok = _fake_resp(status=200, json_data=CATALOG_PAYLOAD)
        err = _fake_resp(status=500, json_data={"error": "boom"})
        sess = _mock_session([ok, err])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            first = await provider.list_image_models()
            second = await provider.list_image_models(force=True)
        # First populated cache, second upstream failed — we serve the
        # cached snapshot rather than an empty list.
        assert second == first

    @pytest.mark.asyncio
    async def test_upstream_error_with_empty_cache_returns_empty(self):
        provider = OpenRouterProvider()
        err = _fake_resp(status=500, json_data={})
        sess = _mock_session([err])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            models = await provider.list_image_models()
        assert models == []
