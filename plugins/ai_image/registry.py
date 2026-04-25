"""Provider registry for AI image generation (F.5a.4).

Lookup by name; raises :class:`ProviderError` with code
``PROVIDER_UNKNOWN`` if the caller supplies a non-existent provider.
"""

from __future__ import annotations

from plugins.ai_image.providers.base import BaseImageProvider, ProviderError
from plugins.ai_image.providers.openai import OpenAIProvider
from plugins.ai_image.providers.openrouter import OpenRouterProvider
from plugins.ai_image.providers.replicate import ReplicateProvider
from plugins.ai_image.providers.stability import StabilityProvider

_PROVIDERS: dict[str, BaseImageProvider] = {
    "openai": OpenAIProvider(),
    "stability": StabilityProvider(),
    "replicate": ReplicateProvider(),
    "openrouter": OpenRouterProvider(),
}


def get_provider(name: str) -> BaseImageProvider:
    """Return the registered provider singleton by name."""
    try:
        return _PROVIDERS[name]
    except KeyError as exc:
        raise ProviderError(
            "PROVIDER_UNKNOWN",
            f"Unknown provider '{name}'. Allowed: {', '.join(_PROVIDERS)}.",
        ) from exc


def list_providers() -> list[str]:
    """Return all registered provider names in registration order."""
    return list(_PROVIDERS.keys())
