"""Base types for AI image providers (F.5a.4).

Each concrete provider subclasses :class:`BaseImageProvider` and implements
``generate()``. Providers return raw image bytes + MIME so the caller (e.g.
the WordPress upload pipeline) can reuse the existing raw-upload path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ProviderError(Exception):
    """Stable-coded error for provider failures.

    Codes follow the F.5a error taxonomy (``PROVIDER_QUOTA``,
    ``PROVIDER_AUTH``, ``PROVIDER_BAD_REQUEST``, ``PROVIDER_UNAVAILABLE``,
    ``PROVIDER_TIMEOUT``). ``details`` is JSON-serialisable.
    """

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"error_code": self.code, "message": self.message, "details": self.details}


@dataclass
class GenerationRequest:
    """Normalised generation parameters.

    Not every provider uses every field — unknown fields are ignored.
    """

    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    model: str | None = None
    negative_prompt: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """Raw bytes + metadata returned by a provider."""

    data: bytes
    mime: str
    filename: str
    meta: dict[str, Any] = field(default_factory=dict)
    cost_usd: float | None = None


class BaseImageProvider(ABC):
    """Abstract provider: turns ``(api_key, request)`` into image bytes."""

    name: str = "base"

    @abstractmethod
    async def generate(self, api_key: str, request: GenerationRequest) -> GenerationResult:
        """Call the provider API and return image bytes + metadata.

        Implementations should raise :class:`ProviderError` with a stable
        code for predictable client handling. Network retries for transient
        failures (429 / 5xx) should happen inside the implementation.
        """
        raise NotImplementedError
