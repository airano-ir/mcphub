"""Contract tests for the public OpenAI-compatible provider seam."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.site_api import normalise_openai_compatible_config
from plugins.ai_image.providers.base import GenerationRequest, ProviderError
from plugins.ai_image.providers.openai_compatible import (
    OpenAICompatibleProvider,
    _supports_edit,
    normalise_model,
)

PNG = b"\x89PNG\r\n\x1a\n"


def test_compatible_base_url_rejects_private_and_plain_http_targets(monkeypatch):
    with pytest.raises(ValueError, match="SSRF"):
        normalise_openai_compatible_config(
            "internal", "openai_compatible", "http://127.0.0.1:8080/v1"
        )
    with pytest.raises(ValueError, match="SSRF"):
        normalise_openai_compatible_config("internal", "openai_compatible", "https://10.0.0.1/v1")

    monkeypatch.setenv("ALLOW_HTTP_PROVIDER_URLS", "true")
    monkeypatch.setattr(
        "plugins.wordpress.handlers._media_security.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    config = normalise_openai_compatible_config(
        "development", "openai_compatible", "http://example.com/v1"
    )
    assert config["base_url"] == "http://example.com/v1"


def response(status: int, payload: dict):
    value = AsyncMock()
    value.status = status
    value.json = AsyncMock(return_value=payload)
    value.text = AsyncMock(return_value="")
    value.headers = {"Content-Type": "image/png"}
    value.read = AsyncMock(return_value=PNG)
    return value


def client_session(session):
    return AsyncMock(
        __aenter__=AsyncMock(return_value=session),
        __aexit__=AsyncMock(return_value=False),
    )


def test_models_are_normalised_and_image_capability_is_preserved():
    model = normalise_model(
        {
            "id": "provider/image-model",
            "name": "Image Model",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text", "image"],
            },
        }
    )
    assert model["id"] == "provider/image-model"
    assert model["supports_image_output"] is True
    assert model["supports_image_edit"] is True


def test_image_edit_requires_explicit_input_and_output_capabilities():
    output_only = normalise_model(
        {
            "id": "provider/output-only",
            "architecture": {"output_modalities": ["image"]},
        }
    )
    assert output_only["supports_image_output"] is True
    assert output_only["supports_image_input"] is False
    assert output_only["supports_image_edit"] is False


def test_heuristic_image_marker_does_not_enable_image_edit():
    model = normalise_model(
        {
            "id": "vendor-flux-text-model",
            "name": "Flux Text Router",
            "description": "Text-only model with image input support.",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"],
            },
        }
    )
    assert model["supports_image_output"] is True
    assert model["supports_image_edit"] is False
    assert _supports_edit(model) is False


@pytest.mark.asyncio
async def test_heuristic_image_marker_is_rejected_for_explicit_and_auto_edit_models():
    model = normalise_model(
        {
            "id": "vendor-flux-text-model",
            "name": "Flux Text Router",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"],
            },
        }
    )
    provider = OpenAICompatibleProvider()
    provider.list_models = AsyncMock(return_value=[model])

    explicit_request = GenerationRequest(
        prompt="edit",
        model=model["id"],
        input_images=[PNG],
        extras={"base_url": "https://api.example.com/v1", "api_type": "openai_images"},
    )
    with pytest.raises(ProviderError) as explicit_error:
        await provider.generate("sk-test", explicit_request)
    assert explicit_error.value.code == "PROVIDER_EDIT_UNSUPPORTED"

    auto_request = GenerationRequest(
        prompt="edit",
        input_images=[PNG],
        extras={"base_url": "https://api.example.com/v1", "api_type": "openai_images"},
    )
    with pytest.raises(ProviderError) as auto_error:
        await provider.generate("sk-test", auto_request)
    assert auto_error.value.code == "PROVIDER_EDIT_UNSUPPORTED"


@pytest.mark.asyncio
async def test_explicit_edit_model_without_capability_fails_before_vendor_call():
    provider = OpenAICompatibleProvider()
    request = GenerationRequest(
        prompt="edit",
        model="provider/output-only",
        input_images=[PNG],
        extras={
            "base_url": "https://api.example.com/v1",
            "api_type": "openai_images",
            "model_capabilities": {
                "supports_image_input": False,
                "supports_image_output": True,
                "supports_image_edit": False,
            },
        },
    )
    with pytest.raises(ProviderError) as exc:
        await provider.generate("sk-test", request)
    assert exc.value.code == "PROVIDER_EDIT_UNSUPPORTED"
    assert exc.value.details["model"] == "provider/output-only"


@pytest.mark.asyncio
async def test_auto_selection_for_edit_ignores_output_only_models():
    provider = OpenAICompatibleProvider()
    provider.list_models = AsyncMock(
        return_value=[
            {"id": "output-only", "supports_image_input": False, "supports_image_output": True},
            {
                "id": "editable",
                "supports_image_input": True,
                "supports_image_output": True,
                "supports_image_edit": True,
            },
        ]
    )
    request = GenerationRequest(
        prompt="edit",
        input_images=[PNG],
        extras={"base_url": "https://api.example.com/v1", "api_type": "openai_images"},
    )
    with patch.object(
        provider,
        "_images",
        AsyncMock(return_value={"data": [{"b64_json": base64.b64encode(PNG).decode()}]}),
    ):
        with patch(
            "plugins.ai_image.providers.openai_compatible._materialise",
            AsyncMock(return_value=(PNG, "image/png")),
        ):
            result = await provider.generate("sk-test", request)
    assert result.meta["model"] == "editable"


@pytest.mark.asyncio
async def test_models_endpoint_imports_all_models_and_uses_auth():
    provider = OpenAICompatibleProvider()
    session = AsyncMock()
    model_response = response(
        200,
        {
            "data": [
                {"id": "text-model"},
                {"id": "image-model", "architecture": {"output_modalities": ["image"]}},
            ]
        },
    )
    session.get = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=model_response),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    with patch(
        "plugins.ai_image.providers.openai_compatible.aiohttp.ClientSession",
        return_value=client_session(session),
    ):
        models = await provider.list_models("sk-test", "https://api.example.com/v1", force=True)
    assert {item["id"] for item in models} == {"image-model", "text-model"}
    assert models[0]["supports_image_output"] is True
    assert session.get.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_image_generation_without_input_uses_json_generation_endpoint():
    provider = OpenAICompatibleProvider()
    session = AsyncMock()
    generate_response = response(
        200,
        {"data": [{"b64_json": base64.b64encode(PNG).decode("ascii")}]},
    )
    session.post = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=generate_response),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    with patch(
        "plugins.ai_image.providers.openai_compatible.aiohttp.ClientSession",
        return_value=client_session(session),
    ):
        result = await provider.generate(
            "sk-test",
            GenerationRequest(
                prompt="a lighthouse",
                model="image-model",
                extras={
                    "base_url": "https://api.example.com/v1",
                    "api_type": "openai_images",
                },
            ),
        )
    assert result.data == PNG
    assert session.post.call_args.args[0].endswith("/images/generations")
    assert session.post.call_args.kwargs["json"]["model"] == "image-model"


@pytest.mark.asyncio
async def test_image_edit_with_input_uses_multipart_edits_endpoint():
    provider = OpenAICompatibleProvider()
    session = AsyncMock()
    edit_response = response(
        200,
        {"data": [{"b64_json": base64.b64encode(PNG).decode("ascii")}]},
    )
    session.post = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=edit_response),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    with patch(
        "plugins.ai_image.providers.openai_compatible.aiohttp.ClientSession",
        return_value=client_session(session),
    ):
        await provider.generate(
            "sk-test",
            GenerationRequest(
                prompt="edit",
                model="image-model",
                input_images=[PNG],
                input_image_mimes=["image/png"],
                extras={
                    "base_url": "https://api.example.com/v1",
                    "api_type": "openai_images",
                    "model_capabilities": {
                        "supports_image_input": True,
                        "supports_image_output": True,
                        "supports_image_edit": True,
                    },
                },
            ),
        )
    kwargs = session.post.call_args.kwargs
    assert "data" in kwargs and "json" not in kwargs
    assert session.post.call_args.args[0].endswith("/images/edits")


@pytest.mark.asyncio
async def test_openai_compatible_chat_endpoint_returns_image_part():
    provider = OpenAICompatibleProvider()
    session = AsyncMock()
    chat_response = response(
        200,
        {
            "choices": [
                {
                    "message": {
                        "images": [
                            {
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64.b64encode(PNG).decode()}"
                                }
                            }
                        ]
                    }
                }
            ]
        },
    )
    session.post = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=chat_response),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    with patch(
        "plugins.ai_image.providers.openai_compatible.aiohttp.ClientSession",
        return_value=client_session(session),
    ):
        result = await provider.generate(
            "sk-test",
            GenerationRequest(
                prompt="a lighthouse",
                model="image-model",
                extras={
                    "base_url": "https://api.example.com/v1",
                    "api_type": "openai_compatible",
                },
            ),
        )
    assert result.data == PNG
    assert session.post.call_args.args[0].endswith("/chat/completions")
    assert session.post.call_args.kwargs["json"]["modalities"] == ["image", "text"]


@pytest.mark.asyncio
async def test_openai_responses_endpoint_uses_image_generation_tool():
    provider = OpenAICompatibleProvider()
    session = AsyncMock()
    responses_response = response(
        200,
        {
            "output": [
                {
                    "type": "image_generation_call",
                    "result": base64.b64encode(PNG).decode(),
                }
            ]
        },
    )
    session.post = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=responses_response),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    with patch(
        "plugins.ai_image.providers.openai_compatible.aiohttp.ClientSession",
        return_value=client_session(session),
    ):
        result = await provider.generate(
            "sk-test",
            GenerationRequest(
                prompt="a lighthouse",
                model="gpt-5.6",
                extras={
                    "base_url": "https://api.example.com/v1",
                    "api_type": "openai_responses",
                },
            ),
        )
    assert result.data == PNG
    assert session.post.call_args.args[0].endswith("/responses")
    payload = session.post.call_args.kwargs["json"]
    assert payload["tools"] == [{"type": "image_generation"}]
