"""P1 image-edit capability contracts across registered providers."""

from __future__ import annotations

import pytest

from plugins.ai_image.providers.base import GenerationRequest, ProviderError
from plugins.ai_image.providers.openrouter import OpenRouterProvider
from plugins.ai_image.providers.replicate import ReplicateProvider
from plugins.ai_image.providers.stability import StabilityProvider


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "provider_name"),
    [
        (StabilityProvider(), "stability"),
        (ReplicateProvider(), "replicate"),
        (OpenRouterProvider(), "openrouter"),
    ],
)
async def test_generation_only_providers_reject_input_images_before_network(
    provider, provider_name
):
    request = GenerationRequest(prompt="edit this", input_images=[b"image"])

    with pytest.raises(ProviderError) as exc:
        await provider.generate("test-key", request)

    assert exc.value.code == "PROVIDER_EDIT_UNSUPPORTED"
    assert exc.value.details["provider"] == provider_name
    assert exc.value.details["capabilities"]["supports_image_input"] is False
    assert exc.value.details["capabilities"]["supports_image_output"] is True
