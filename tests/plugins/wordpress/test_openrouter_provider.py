"""F.5a.9 partial — Tests for the OpenRouter image-generation provider."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import pytest

from plugins.ai_image.providers.base import GenerationRequest, ProviderError
from plugins.ai_image.providers.openrouter import (
    OpenRouterProvider,
    _extract_image_url,
    _image_url_from_entry,
)
from plugins.ai_image.registry import get_provider, list_providers

_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _mock_session_post(responses: list):
    """Build a fake aiohttp.ClientSession whose .post/.get cycle responses."""
    iterator = iter(responses)

    def _request(*_args, **_kwargs):
        resp = next(iterator)
        return AsyncMock(
            __aenter__=AsyncMock(return_value=resp),
            __aexit__=AsyncMock(return_value=False),
        )

    sess = AsyncMock()
    sess.post = _request
    sess.get = _request
    return sess


def _fake_resp(*, status: int, json_data=None, text_data="", raw=None, headers=None):
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text_data or "")
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    if raw is not None:
        resp.read = AsyncMock(return_value=raw)
    resp.headers = headers or {}
    return resp


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_openrouter_is_registered(self):
        assert "openrouter" in list_providers()

    def test_registry_lookup_returns_singleton(self):
        p = get_provider("openrouter")
        assert p.name == "openrouter"
        assert p is get_provider("openrouter")  # same instance


# ---------------------------------------------------------------------------
# Response-shape parsers (pure, no network)
# ---------------------------------------------------------------------------


class TestImageUrlExtraction:
    def test_image_url_from_dict_url(self):
        entry = {"image_url": {"url": "data:image/png;base64,AAAA"}}
        assert _image_url_from_entry(entry) == "data:image/png;base64,AAAA"

    def test_image_url_from_string(self):
        entry = {"image_url": "https://x.example/y.png"}
        assert _image_url_from_entry(entry) == "https://x.example/y.png"

    def test_image_url_bare_url_field(self):
        assert (
            _image_url_from_entry({"url": "https://z.example/a.png"}) == "https://z.example/a.png"
        )

    def test_image_url_from_junk(self):
        assert _image_url_from_entry(None) is None
        assert _image_url_from_entry({"image_url": 42}) is None

    def test_extract_gemini_shape_message_images(self):
        body = {
            "choices": [
                {"message": {"images": [{"image_url": {"url": "data:image/png;base64,Zm9v"}}]}}
            ]
        }
        assert _extract_image_url(body) == "data:image/png;base64,Zm9v"

    def test_extract_multimodal_content_parts(self):
        body = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "here's your image"},
                            {"type": "image_url", "image_url": {"url": "https://x/y.png"}},
                        ]
                    }
                }
            ]
        }
        assert _extract_image_url(body) == "https://x/y.png"

    def test_extract_no_image_returns_none(self):
        body = {"choices": [{"message": {"content": "just text"}}]}
        assert _extract_image_url(body) is None

    def test_extract_empty_choices(self):
        assert _extract_image_url({"choices": []}) is None
        assert _extract_image_url({}) is None


# ---------------------------------------------------------------------------
# Provider.generate — auth / request shape
# ---------------------------------------------------------------------------


class TestOpenRouterProvider:
    @pytest.mark.asyncio
    async def test_missing_api_key_raises_auth(self):
        provider = OpenRouterProvider()
        with pytest.raises(ProviderError) as e:
            await provider.generate("", GenerationRequest(prompt="x"))
        assert e.value.code == "PROVIDER_AUTH"

    @pytest.mark.asyncio
    async def test_happy_path_gemini_data_url(self):
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
                ],
                "usage": {"total_tokens": 128},
            },
        )
        sess = _mock_session_post([ok])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await provider.generate(
                "or-test",
                GenerationRequest(prompt="a cat"),
            )
        assert result.data == _PNG_1x1
        assert result.mime == "image/png"
        assert "gemini" in result.filename
        assert result.meta.get("total_tokens") == 128
        # F.X.fix #11: known model → non-null cost_usd from _MODEL_PRICING.
        assert result.cost_usd is not None
        assert result.cost_usd > 0

    @pytest.mark.asyncio
    async def test_http_url_is_fetched(self):
        provider = OpenRouterProvider()
        gen_resp = _fake_resp(
            status=200,
            json_data={
                "choices": [
                    {"message": {"images": [{"image_url": {"url": "https://cdn.example/out.png"}}]}}
                ]
            },
        )
        fetch_resp = _fake_resp(
            status=200,
            raw=_PNG_1x1,
            headers={"Content-Type": "image/png"},
        )
        sess = _mock_session_post([gen_resp, fetch_resp])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await provider.generate("or-test", GenerationRequest(prompt="x"))
        assert result.data == _PNG_1x1
        assert result.mime == "image/png"

    @pytest.mark.asyncio
    async def test_no_image_raises_bad_response(self):
        provider = OpenRouterProvider()
        empty = _fake_resp(
            status=200,
            json_data={"choices": [{"message": {"content": "no image for you"}}]},
        )
        sess = _mock_session_post([empty])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(ProviderError) as e:
                await provider.generate("or-test", GenerationRequest(prompt="x"))
        assert e.value.code == "PROVIDER_BAD_RESPONSE"

    @pytest.mark.asyncio
    async def test_401_maps_to_provider_auth(self):
        provider = OpenRouterProvider()
        r401 = _fake_resp(status=401, text_data="invalid key")
        sess = _mock_session_post([r401])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(ProviderError) as e:
                await provider.generate("bad-key", GenerationRequest(prompt="x"))
        assert e.value.code == "PROVIDER_AUTH"

    @pytest.mark.asyncio
    async def test_400_maps_to_provider_bad_request(self):
        provider = OpenRouterProvider()
        r400 = _fake_resp(status=400, text_data="model not found")
        sess = _mock_session_post([r400])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(ProviderError) as e:
                await provider.generate(
                    "or-test",
                    GenerationRequest(prompt="x", model="nonexistent/model"),
                )
        assert e.value.code == "PROVIDER_BAD_REQUEST"

    @pytest.mark.asyncio
    async def test_429_retried_then_succeeds(self):
        provider = OpenRouterProvider()
        b64 = base64.b64encode(_PNG_1x1).decode()
        r429 = _fake_resp(status=429, text_data="slow down")
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
        sess = _mock_session_post([r429, ok])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with patch("plugins.ai_image.providers.openrouter.asyncio.sleep", AsyncMock()):
                result = await provider.generate("or-test", GenerationRequest(prompt="x"))
        assert result.data == _PNG_1x1

    @pytest.mark.asyncio
    async def test_persistent_5xx_raises_unavailable(self):
        provider = OpenRouterProvider()
        r500 = _fake_resp(status=500, text_data="boom")
        sess = _mock_session_post([r500, r500, r500])
        with patch("plugins.ai_image.providers.openrouter.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with patch("plugins.ai_image.providers.openrouter.asyncio.sleep", AsyncMock()):
                with pytest.raises(ProviderError) as e:
                    await provider.generate("or-test", GenerationRequest(prompt="x"))
        assert e.value.code == "PROVIDER_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_negative_prompt_appended_to_user_content(self, monkeypatch):
        """Negative prompt is inlined into the user message as 'Avoid: ...'."""
        provider = OpenRouterProvider()
        captured: dict = {}

        async def _mock_post_with_retry(self, api_key, payload):
            captured["payload"] = payload
            b64 = base64.b64encode(_PNG_1x1).decode()
            return {
                "choices": [
                    {
                        "message": {
                            "images": [{"image_url": {"url": f"data:image/png;base64,{b64}"}}]
                        }
                    }
                ]
            }

        monkeypatch.setattr(
            OpenRouterProvider, "_post_with_retry", _mock_post_with_retry, raising=True
        )
        await provider.generate(
            "or-test",
            GenerationRequest(prompt="a cat", negative_prompt="no dogs"),
        )
        user_msg = captured["payload"]["messages"][0]["content"]
        assert "a cat" in user_msg
        assert "Avoid: no dogs" in user_msg
