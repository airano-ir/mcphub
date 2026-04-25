"""F.X.fix #11 — OpenRouter pricing table for cost_usd attribution."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from plugins.ai_image.providers.base import GenerationRequest, ProviderError
from plugins.ai_image.providers.openrouter import (
    _MODEL_PRICING,
    OpenRouterProvider,
    _cost_for,
    _pricing_table,
)

_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _fake_resp(*, status, json_data=None, text_data="", raw=None, headers=None):
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text_data or "")
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    if raw is not None:
        resp.read = AsyncMock(return_value=raw)
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
    sess.post = _request
    sess.get = _request
    return sess


class TestPricingTable:
    def test_known_model_maps_to_non_null_cost(self):
        assert _cost_for("google/gemini-2.5-flash-image") is not None
        assert _cost_for("google/gemini-2.5-flash-image") > 0

    def test_unknown_model_returns_none(self, caplog):
        assert _cost_for("nonexistent/model-xyz") is None

    def test_gemini_preview_still_priced(self):
        # Preview alias is deprecated but still has a price entry so if
        # an admin call bypasses the generate-time guard the cost column
        # is still usable for audit.
        assert _cost_for("google/gemini-2.5-flash-image-preview") is not None

    def test_pricing_table_contains_expected_providers(self):
        ids = set(_MODEL_PRICING.keys())
        assert any(m.startswith("google/gemini-") for m in ids)
        assert any(m.startswith("openai/dall-e") for m in ids)
        assert any(m.startswith("black-forest-labs/flux") for m in ids)

    def test_env_override_merges_and_wins(self, monkeypatch):
        monkeypatch.setenv(
            "OPENROUTER_PRICING_OVERRIDE",
            json.dumps({"google/gemini-2.5-flash-image": 0.001, "custom/model": 0.5}),
        )
        table = _pricing_table()
        assert table["google/gemini-2.5-flash-image"] == 0.001
        assert table["custom/model"] == 0.5
        # Untouched entries stay from the hard-coded table.
        assert "openai/dall-e-3" in table

    def test_env_override_bad_json_is_ignored(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_PRICING_OVERRIDE", "not-json{")
        # Falls back to the default table, no exception.
        assert (
            _pricing_table()["google/gemini-2.5-flash-image"]
            == _MODEL_PRICING["google/gemini-2.5-flash-image"]
        )


class TestGenerateAttributesCost:
    @pytest.mark.asyncio
    async def test_cost_usd_populated_for_known_model(self):
        provider = OpenRouterProvider()
        b64 = base64.b64encode(_PNG_1x1).decode()
        ok = _fake_resp(
            status=200,
            json_data={
                "choices": [
                    {
                        "message": {
                            "images": [{"image_url": {"url": f"data:image/png;base64,{b64}"}}]
                        }
                    }
                ]
            },
        )
        sess = _mock_session([ok])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await provider.generate("k", GenerationRequest(prompt="x"))
        assert result.cost_usd == _MODEL_PRICING["google/gemini-2.5-flash-image"]

    @pytest.mark.asyncio
    async def test_cost_usd_null_for_unknown_model(self):
        provider = OpenRouterProvider()
        b64 = base64.b64encode(_PNG_1x1).decode()
        ok = _fake_resp(
            status=200,
            json_data={
                "choices": [
                    {
                        "message": {
                            "images": [{"image_url": {"url": f"data:image/png;base64,{b64}"}}]
                        }
                    }
                ]
            },
        )
        sess = _mock_session([ok])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await provider.generate(
                "k", GenerationRequest(prompt="x", model="weird/unreleased-model")
            )
        assert result.cost_usd is None


class TestDeprecatedModelGuard:
    @pytest.mark.asyncio
    async def test_preview_model_raises_model_deprecated(self):
        provider = OpenRouterProvider()
        with pytest.raises(ProviderError) as e:
            await provider.generate(
                "k",
                GenerationRequest(prompt="x", model="google/gemini-2.5-flash-image-preview"),
            )
        assert e.value.code == "PROVIDER_MODEL_DEPRECATED"
        assert "google/gemini-2.5-flash-image" in str(e.value.message)
        assert e.value.details.get("replacement_model") == "google/gemini-2.5-flash-image"
