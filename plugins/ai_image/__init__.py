"""AI image generation provider library (F.5a.4).

Not a registered MCP plugin — this package exposes provider
implementations and a lookup registry consumed by media-upload tools in
other plugins (currently ``wordpress_generate_and_upload_image``).

Typical usage::

    from plugins.ai_image.registry import get_provider

    provider = get_provider("openai")
    result = await provider.generate(
        api_key=key, prompt="a red cube", size="1024x1024"
    )
    image_bytes, mime, meta = result.bytes, result.mime, result.meta
"""

from plugins.ai_image.providers.base import (
    BaseImageProvider,
    GenerationRequest,
    GenerationResult,
    ProviderError,
)
from plugins.ai_image.registry import get_provider, list_providers

__all__ = [
    "BaseImageProvider",
    "GenerationRequest",
    "GenerationResult",
    "ProviderError",
    "get_provider",
    "list_providers",
]
