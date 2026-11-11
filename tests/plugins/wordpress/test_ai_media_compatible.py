from unittest.mock import AsyncMock

import pytest

from plugins.ai_image.providers.base import GenerationResult
from plugins.wordpress.handlers.ai_media import AIMediaHandler


@pytest.mark.asyncio
async def test_compatible_connection_config_is_passed_to_provider(monkeypatch):
    client = AsyncMock()
    client.site_url = "https://wp.example.com"
    handler = AIMediaHandler(client, user_id="user-1", site_id="site-1")
    provider = AsyncMock()
    provider.generate = AsyncMock(
        return_value=GenerationResult(data=b"image", mime="image/png", filename="x.png")
    )
    monkeypatch.setattr(
        "plugins.wordpress.handlers.ai_media.get_provider",
        lambda name: provider,
    )
    monkeypatch.setattr(
        "plugins.wordpress.handlers.ai_media.get_site_ai_provider_secret",
        AsyncMock(
            return_value=(
                {
                    "base_url": "https://gateway.example/v1",
                    "api_type": "openai_compatible",
                    "model_id": "provider/image-model",
                },
                "sk-secret",
            )
        ),
    )
    monkeypatch.setattr(
        "plugins.wordpress.handlers.ai_media.wp_raw_upload",
        AsyncMock(return_value={"id": 1, "source_url": "https://wp.example/image.png"}),
    )
    monkeypatch.setattr(
        "plugins.wordpress.handlers.ai_media._apply_metadata_and_attach",
        AsyncMock(return_value={}),
    )

    result = await handler.generate_and_upload_image(
        provider="openai_compatible",
        connection_id="connection-1",
        prompt="a lighthouse",
    )

    assert '"id": 1' in result
    request = provider.generate.call_args.args[1]
    assert request.model == "provider/image-model"
    assert request.extras == {
        "base_url": "https://gateway.example/v1",
        "api_type": "openai_compatible",
        "model_id": "provider/image-model",
        "connection_id": "connection-1",
    }
    assert provider.generate.call_args.args[0] == "sk-secret"


@pytest.mark.asyncio
async def test_compatible_provider_requires_connection_id(monkeypatch):
    handler = AIMediaHandler(AsyncMock(), user_id="user-1", site_id="site-1")
    result = await handler.generate_and_upload_image(
        provider="openai_compatible",
        prompt="a lighthouse",
    )
    assert "NO_PROVIDER_CONFIG" in result
