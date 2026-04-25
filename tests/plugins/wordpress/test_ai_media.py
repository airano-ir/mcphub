"""Tests for F.5a.4 AI image generation + upload chain."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from core.database import Database
from plugins.ai_image.providers.base import (
    GenerationRequest,
    GenerationResult,
    ProviderError,
)
from plugins.ai_image.providers.openai import OpenAIProvider
from plugins.ai_image.registry import get_provider, list_providers
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.ai_media import AIMediaHandler

_TEST_KEY_B64 = base64.b64encode(b"0" * 32).decode()

# 1x1 PNG
_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "ai_test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def user_row(db):
    return await db.create_user(
        email="alice@example.com",
        name="Alice",
        provider="github",
        provider_id="gh-ai",
    )


# --- Registry ---------------------------------------------------------------


class TestRegistry:
    def test_lists_expected_providers(self):
        # Registry is the source of truth now that the per-user
        # user_provider_keys module has been removed (F.5a.9.x).
        # F.5a.9 partial: OpenRouter added.
        assert set(list_providers()) == {"openai", "stability", "replicate", "openrouter"}

    def test_get_provider_known(self):
        assert get_provider("openai").name == "openai"

    def test_get_provider_unknown_raises(self):
        with pytest.raises(ProviderError) as e:
            get_provider("midjourney")
        assert e.value.code == "PROVIDER_UNKNOWN"


# Per-user UserProviderKeyManager removed in F.5a.9.x. Per-site equivalents
# live in ``tests/test_site_provider_keys.py``.


# --- OpenAI provider --------------------------------------------------------


def _mock_session_post(responses: list):
    """Build a fake aiohttp.ClientSession whose .post() cycles through responses."""
    iterator = iter(responses)

    def _post(*_args, **_kwargs):
        resp = next(iterator)
        return AsyncMock(
            __aenter__=AsyncMock(return_value=resp),
            __aexit__=AsyncMock(return_value=False),
        )

    sess = AsyncMock()
    sess.post = _post
    sess.get = _post  # reuse for URL fetches
    return sess


def _fake_resp(*, status: int, json_data=None, text_data=None, raw=None):
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text_data or (json.dumps(json_data) if json_data else ""))
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    if raw is not None:
        resp.read = AsyncMock(return_value=raw)
    return resp


class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_dalle_url_fetched_and_returned_as_bytes(self):
        provider = OpenAIProvider()
        generate_resp = _fake_resp(
            status=200,
            json_data={
                "data": [
                    {
                        "url": "https://oaidalle.example.com/img/abc.png",
                        "revised_prompt": "revised",
                    }
                ]
            },
        )
        fetch_resp = _fake_resp(status=200, raw=_PNG_1x1)
        sess = _mock_session_post([generate_resp, fetch_resp])
        with patch("plugins.ai_image.providers.openai.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await provider.generate(
                "sk-test",
                GenerationRequest(prompt="a cube", size="1024x1024"),
            )
        assert result.data == _PNG_1x1
        assert result.mime == "image/png"
        assert result.meta.get("revised_prompt") == "revised"
        assert result.cost_usd == 0.040

    @pytest.mark.asyncio
    async def test_missing_key_raises_auth(self):
        provider = OpenAIProvider()
        with pytest.raises(ProviderError) as e:
            await provider.generate("", GenerationRequest(prompt="x"))
        assert e.value.code == "PROVIDER_AUTH"

    @pytest.mark.asyncio
    async def test_429_retried_then_succeeds(self):
        provider = OpenAIProvider()
        r429 = _fake_resp(status=429, text_data="slow down")
        ok = _fake_resp(
            status=200,
            json_data={"data": [{"b64_json": base64.b64encode(_PNG_1x1).decode()}]},
        )
        sess = _mock_session_post([r429, ok])
        with patch("plugins.ai_image.providers.openai.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with patch("plugins.ai_image.providers.openai.asyncio.sleep", AsyncMock()):
                result = await provider.generate(
                    "sk-test",
                    GenerationRequest(prompt="x", model="gpt-image-1"),
                )
        assert result.data == _PNG_1x1

    @pytest.mark.asyncio
    async def test_persistent_5xx_becomes_unavailable(self):
        provider = OpenAIProvider()
        r500 = _fake_resp(status=500, text_data="boom")
        sess = _mock_session_post([r500, r500, r500])
        with patch("plugins.ai_image.providers.openai.aiohttp.ClientSession") as cls:
            cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with patch("plugins.ai_image.providers.openai.asyncio.sleep", AsyncMock()):
                with pytest.raises(ProviderError) as e:
                    await provider.generate("sk", GenerationRequest(prompt="x"))
        assert e.value.code == "PROVIDER_UNAVAILABLE"


# --- AIMediaHandler ---------------------------------------------------------


class TestAIMediaHandler:
    @pytest.mark.asyncio
    async def test_missing_api_key_returns_typed_error(self, wp_client, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        handler = AIMediaHandler(wp_client, user_id=None)

        async def _noop(*_a, **_kw):
            return None

        # Force the key resolver to return None without needing a real DB.
        monkeypatch.setattr(handler, "_resolve_api_key", AsyncMock(return_value=None))
        out = await handler.generate_and_upload_image(provider="openai", prompt="x")
        data = json.loads(out)
        assert data["error_code"] == "NO_PROVIDER_KEY"

    @pytest.mark.asyncio
    async def test_happy_path_chains_to_upload(self, wp_client, monkeypatch):
        handler = AIMediaHandler(wp_client, user_id="u1")
        monkeypatch.setattr(handler, "_resolve_api_key", AsyncMock(return_value="sk"))

        fake_result = GenerationResult(
            data=_PNG_1x1,
            mime="image/png",
            filename="ai.png",
            meta={"model": "dall-e-3"},
            cost_usd=0.04,
        )
        monkeypatch.setattr(
            "plugins.wordpress.handlers.ai_media.get_provider",
            lambda name: _StubProvider(fake_result),
        )
        upload_mock = AsyncMock(
            return_value={
                "id": 42,
                "title": {"rendered": "ai"},
                "source_url": "https://wp.example.com/ai.png",
                "mime_type": "image/png",
                "media_type": "image",
            }
        )
        monkeypatch.setattr("plugins.wordpress.handlers.ai_media.wp_raw_upload", upload_mock)

        # Disable optimize (skip_optimize=True skips Pillow and keeps test hermetic).
        out = await handler.generate_and_upload_image(
            provider="openai", prompt="x", skip_optimize=True
        )
        data = json.loads(out)
        assert data["id"] == 42
        assert data["provider"] == "openai"
        assert data["cost_usd"] == 0.04
        assert upload_mock.await_count == 1

    @pytest.mark.asyncio
    async def test_provider_error_surfaced_with_code(self, wp_client, monkeypatch):
        handler = AIMediaHandler(wp_client, user_id="u1")
        monkeypatch.setattr(handler, "_resolve_api_key", AsyncMock(return_value="sk"))
        monkeypatch.setattr(
            "plugins.wordpress.handlers.ai_media.get_provider",
            lambda name: _StubProvider(exc=ProviderError("PROVIDER_QUOTA", "rate")),
        )
        out = await handler.generate_and_upload_image(provider="openai", prompt="x")
        data = json.loads(out)
        assert data["error_code"] == "PROVIDER_QUOTA"

    @pytest.mark.asyncio
    async def test_audit_entry_emitted_on_success(self, wp_client, monkeypatch):
        handler = AIMediaHandler(wp_client, user_id="u1")
        monkeypatch.setattr(handler, "_resolve_api_key", AsyncMock(return_value="sk"))
        monkeypatch.setattr(
            "plugins.wordpress.handlers.ai_media.get_provider",
            lambda name: _StubProvider(
                GenerationResult(
                    data=_PNG_1x1,
                    mime="image/png",
                    filename="ai.png",
                    meta={"model": "dall-e-3"},
                    cost_usd=0.04,
                )
            ),
        )
        monkeypatch.setattr(
            "plugins.wordpress.handlers.ai_media.wp_raw_upload",
            AsyncMock(
                return_value={
                    "id": 7,
                    "title": {"rendered": ""},
                    "source_url": "https://x/img.png",
                    "mime_type": "image/png",
                    "media_type": "image",
                }
            ),
        )

        calls: list[dict] = []

        class _FakeAudit:
            def log_tool_call(self, **kwargs):
                calls.append(kwargs)

        monkeypatch.setattr(
            "core.audit_log.get_audit_logger",
            lambda: _FakeAudit(),
        )

        await handler.generate_and_upload_image(provider="openai", prompt="x", skip_optimize=True)

        # F.5a.6.4: AI uploads emit BOTH the legacy provider-cost entry and a
        # unified media.upload entry. Find each by tool_name.
        ai_call = next(c for c in calls if c["tool_name"] == "wordpress_generate_and_upload_image")
        assert ai_call["params"]["provider"] == "openai"
        assert ai_call["params"]["cost_usd"] == 0.04
        assert ai_call["user_id"] == "u1"

        media_call = next(c for c in calls if c["tool_name"] == "media.upload")
        assert media_call["params"]["source"] == "ai:openai"
        assert media_call["params"]["cost_usd"] == 0.04
        assert media_call["params"]["media_id"] == 7


class TestResolverSiteScope:
    """F.5a.9.x: ``_resolve_api_key`` reads from the per-site key store when
    ``site_id`` is set, and falls back to env vars only when it is None."""

    @pytest.mark.asyncio
    async def test_site_key_wins_over_env(self, wp_client, monkeypatch):
        """With site_id set, the per-site key is returned even if env has one."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-should-not-be-used")

        async def _fake_get(site_id, provider):
            assert site_id == "site-abc"
            assert provider == "openai"
            return "sk-site-win"

        monkeypatch.setattr("core.site_api.get_site_provider_key", _fake_get)

        handler = AIMediaHandler(wp_client, user_id="u1", site_id="site-abc")
        assert await handler._resolve_api_key("openai") == "sk-site-win"

    @pytest.mark.asyncio
    async def test_site_set_but_no_key_returns_none(self, wp_client, monkeypatch):
        """site_id set + no site key stored + env present → still None.
        Env fallback is deliberately not applied on the per-site path."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-ignored")

        async def _fake_get(site_id, provider):
            return None

        monkeypatch.setattr("core.site_api.get_site_provider_key", _fake_get)

        handler = AIMediaHandler(wp_client, user_id="u1", site_id="site-abc")
        assert await handler._resolve_api_key("openai") is None

    @pytest.mark.asyncio
    async def test_no_site_id_falls_back_to_env(self, wp_client, monkeypatch):
        """site_id=None (admin / master-key path): env var is used."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-admin-env")

        handler = AIMediaHandler(wp_client, user_id=None, site_id=None)
        assert await handler._resolve_api_key("openai") == "sk-admin-env"

    @pytest.mark.asyncio
    async def test_no_site_id_no_env_returns_none(self, wp_client, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        handler = AIMediaHandler(wp_client, user_id=None, site_id=None)
        assert await handler._resolve_api_key("openai") is None

    @pytest.mark.asyncio
    async def test_missing_key_error_points_to_site_dashboard(self, wp_client, monkeypatch):
        """When site_id is set and no key, error message points at the site
        edit page, not the deprecated /dashboard/provider-keys page."""

        async def _fake_get(site_id, provider):
            return None

        monkeypatch.setattr("core.site_api.get_site_provider_key", _fake_get)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        handler = AIMediaHandler(wp_client, user_id="u1", site_id="site-xyz")
        out = await handler.generate_and_upload_image(provider="openai", prompt="x")
        data = json.loads(out)
        assert data["error_code"] == "NO_PROVIDER_KEY"
        assert data["dashboard_url"] == "/dashboard/sites/site-xyz"
        assert "/dashboard/provider-keys" not in json.dumps(data)


class _StubProvider:
    """Minimal provider stub used by AIMediaHandler tests."""

    name = "stub"

    def __init__(
        self,
        result: GenerationResult | None = None,
        exc: ProviderError | None = None,
    ):
        self._result = result
        self._exc = exc

    async def generate(self, api_key: str, request: GenerationRequest) -> GenerationResult:
        if self._exc is not None:
            raise self._exc
        assert self._result is not None
        return self._result
