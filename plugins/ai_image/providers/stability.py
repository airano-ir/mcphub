"""Stability AI image generation provider (Stable Image Core / Ultra).

Uses the v2beta generate endpoint with ``Accept: image/*`` to get raw
bytes back directly (no JSON indirection).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from plugins.ai_image.providers.base import (
    BaseImageProvider,
    GenerationRequest,
    GenerationResult,
    ProviderError,
)

_logger = logging.getLogger("mcphub.ai_image.stability")

_MODEL_ENDPOINTS = {
    "core": "https://api.stability.ai/v2beta/stable-image/generate/core",
    "ultra": "https://api.stability.ai/v2beta/stable-image/generate/ultra",
    "sd3": "https://api.stability.ai/v2beta/stable-image/generate/sd3",
}
_DEFAULT_MODEL = "core"
_MAX_RETRIES = 3
_REQUEST_TIMEOUT = 120
_RETRY_STATUS = {429, 500, 502, 503, 504}

_COST_TABLE: dict[str, float] = {
    "core": 0.03,
    "ultra": 0.08,
    "sd3": 0.065,
}


def _size_to_aspect(size: str) -> str:
    """Map a WxH size string to the Stability aspect_ratio enum."""
    mapping = {
        "1024x1024": "1:1",
        "1152x896": "21:9",
        "1216x832": "3:2",
        "1344x768": "16:9",
        "768x1344": "9:16",
        "832x1216": "2:3",
        "1024x576": "16:9",
        "512x512": "1:1",
    }
    return mapping.get(size, "1:1")


class StabilityProvider(BaseImageProvider):
    name = "stability"

    async def generate(self, api_key: str, request: GenerationRequest) -> GenerationResult:
        if not api_key:
            raise ProviderError("PROVIDER_AUTH", "Stability API key is missing.")

        model = (request.model or _DEFAULT_MODEL).lower()
        endpoint = _MODEL_ENDPOINTS.get(model)
        if endpoint is None:
            raise ProviderError(
                "PROVIDER_BAD_REQUEST",
                f"Unknown Stability model '{model}'. " f"Allowed: {', '.join(_MODEL_ENDPOINTS)}.",
            )

        form = aiohttp.FormData()
        form.add_field("prompt", request.prompt)
        form.add_field("output_format", "png")
        form.add_field("aspect_ratio", _size_to_aspect(request.size))
        if request.negative_prompt:
            form.add_field("negative_prompt", request.negative_prompt)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "image/*",
        }
        data, meta = await self._post_with_retry(endpoint, form, headers)

        meta = dict(meta)
        meta["model"] = model
        meta["aspect_ratio"] = _size_to_aspect(request.size)
        return GenerationResult(
            data=data,
            mime="image/png",
            filename=f"stability-{model}.png",
            meta=meta,
            cost_usd=_COST_TABLE.get(model),
        )

    async def _post_with_retry(
        self,
        endpoint: str,
        form: aiohttp.FormData,
        headers: dict[str, str],
    ) -> tuple[bytes, dict[str, Any]]:
        last_error: str = ""
        delay = 1.0
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    async with session.post(endpoint, data=form, headers=headers) as resp:
                        if resp.status == 200:
                            body = await resp.read()
                            return body, {"attempt": attempt, "status": 200}
                        text = await resp.text()
                        last_error = text[:500]
                        if resp.status == 401 or resp.status == 403:
                            raise ProviderError(
                                "PROVIDER_AUTH",
                                f"Stability rejected auth ({resp.status}).",
                                {"body": last_error},
                            )
                        if resp.status == 400:
                            raise ProviderError(
                                "PROVIDER_BAD_REQUEST",
                                f"Stability rejected request: {last_error}",
                                {"body": last_error},
                            )
                        if resp.status in _RETRY_STATUS and attempt < _MAX_RETRIES:
                            _logger.warning("Stability %d, retry %d", resp.status, attempt)
                            await asyncio.sleep(delay)
                            delay *= 2
                            continue
                        if resp.status == 429:
                            raise ProviderError(
                                "PROVIDER_QUOTA",
                                "Stability quota/rate-limit hit.",
                                {"status": 429, "body": last_error},
                            )
                        raise ProviderError(
                            "PROVIDER_UNAVAILABLE",
                            f"Stability upstream error HTTP {resp.status}.",
                            {"status": resp.status, "body": last_error},
                        )
                except TimeoutError as exc:
                    last_error = f"timeout: {exc}"
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue
                    raise ProviderError(
                        "PROVIDER_TIMEOUT",
                        "Stability request timed out after retries.",
                    ) from exc
        raise ProviderError(
            "PROVIDER_UNAVAILABLE",
            f"Stability call failed after {_MAX_RETRIES} attempts: {last_error}",
        )
